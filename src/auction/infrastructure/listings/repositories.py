# 매물 Repository의 SQLAlchemy 구현체다.
# domain 인터페이스를 구현하며 ORM 모델과 도메인 엔티티를 변환한다.
# DB 세션은 외부에서 받으며 commit·rollback은 트랜잭션 담당자가 처리한다.
# 대기열·마감 목록은 후보 조회다. 변경 전에는 잠금 조회 후 상태를 다시 검사한다.
# save는 flush 후 새 엔티티를 반환하므로 반환값을 사용한다.
#
# [TO DO] DB 제약 위반(IntegrityError)을 업무 오류로 변환할지 정한다. (진행 전)
# [ ] 실제 PostgreSQL에서 조회·저장·동시성 테스트

from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from auction.domain.listings.entities import Listing, ListingStatus
from auction.domain.listings.repositories import ListingRepository
from auction.infrastructure.listings.models import ListingModel
from shared.core.exceptions import NotFoundError

# 아이템 종류 잠금의 이름공간이다. 다른 도메인의 advisory lock 키와 겹치지 않게 한다.
# users는 731401을 사용한다. (lock_administration)
_DEFINITION_LOCK_NAMESPACE = 731402


class SqlAlchemyListingRepository(ListingRepository):
    def __init__(self, session: AsyncSession, *, page_size: int):
        if page_size < 1:
            raise ValueError("페이지당 개수는 1 이상이어야 합니다.")

        self.session = session
        self.page_size = page_size

    # [AUC-03] 매물 상세 정보가 필요할 때 조회한다.
    async def get(self, listing_id: int) -> Listing | None:
        model = await self.session.get(ListingModel, listing_id)
        return self._to_entity(model) if model is not None else None

    # [AUC-04, AUC-05, AUC-11] 변경 전에 잠금을 얻고 최신 상태를 읽는다.
    async def get_for_update(self, listing_id: int) -> Listing | None:
        statement = (
            select(ListingModel)
            .where(ListingModel.id == listing_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        model = await self.session.scalar(statement)
        return self._to_entity(model) if model is not None else None

    # [AUC-02] 공개 중인 매물을 공개 시각 최신순으로 조회한다.
    async def list_bidding(self, page: int) -> list[Listing]:
        if page < 1:
            raise ValueError("페이지 번호는 1 이상이어야 합니다.")

        statement = (
            select(ListingModel)
            .where(ListingModel.status == ListingStatus.BIDDING.value)
            .order_by(ListingModel.started_at.desc(), ListingModel.id.desc())
            .offset((page - 1) * self.page_size)
            .limit(self.page_size)
        )
        models = (await self.session.scalars(statement)).all()
        return [self._to_entity(model) for model in models]

    # 전달된 필터를 모두 만족하는 매물을 페이지별로 조회한다.
    # 등록 시각 최신순으로 정렬하고, 결과를 Listing 목록으로 반환한다.
    async def list_filtered(
        self,
        page: int,
        *,
        listing_id: int | None = None,
        item_definition_id: int | None = None,
        inventory_item_id: int | None = None,
        status: ListingStatus | None = None,
    ) -> list[Listing]:
        if page < 1:
            raise ValueError("페이지 번호는 1 이상이어야 합니다.")

        statement = select(ListingModel)

        # 값이 전달된 조건만 추가한다. 조건들은 AND로 연결된다.
        filters = (
            (ListingModel.id, listing_id),
            (ListingModel.item_definition_id, item_definition_id),
            (ListingModel.inventory_item_id, inventory_item_id),
            (ListingModel.status, status.value if status is not None else None),
        )
        for column, value in filters:
            if value is not None:
                statement = statement.where(column == value)

        # 같은 등록 시각에도 순서가 일정하도록 ID를 함께 정렬한다.
        statement = (
            statement
            .order_by(ListingModel.created_at.desc(), ListingModel.id.desc())
            .offset((page - 1) * self.page_size)
            .limit(self.page_size)
        )

        models = (await self.session.scalars(statement)).all()
        return [self._to_entity(model) for model in models]

    # [AUC-01, AUC-06] 같은 아이템 종류의 공개 판단을 트랜잭션 단위로 직렬화한다.
    # 입력: 아이템 종류 ID. 처리: PostgreSQL 트랜잭션 advisory lock을 획득한다.
    # 반환값 없음. 다른 트랜잭션이 잡고 있으면 끝날 때까지 기다리고, commit·rollback 시 풀린다.
    async def lock_definition(self, item_definition_id: int) -> None:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(:namespace, :key)"),
            {"namespace": _DEFINITION_LOCK_NAMESPACE, "key": item_definition_id},
        )

    # [AUC-01, AUC-06] 같은 종류의 매물이 이미 공개 중인지 확인한다.
    async def exists_bidding(self, item_definition_id: int) -> bool:
        query = select(ListingModel.id).where(
            ListingModel.item_definition_id == item_definition_id,
            ListingModel.status == ListingStatus.BIDDING.value,
        )
        return bool(await self.session.scalar(select(query.exists())))

    # [AUC-06] 다음 공개 후보로 가장 오래된 대기 매물을 조회한다.
    async def next_queued(self, item_definition_id: int) -> Listing | None:
        statement = (
            select(ListingModel)
            .where(
                ListingModel.item_definition_id == item_definition_id,
                ListingModel.status == ListingStatus.QUEUED.value,
            )
            .order_by(ListingModel.created_at, ListingModel.id)
            .limit(1)
        )
        model = await self.session.scalar(statement)
        return self._to_entity(model) if model is not None else None

    # [AUC-05] 마감 시각에 도달한 진행 매물을 처리 후보로 조회한다.
    async def list_expired_bidding(self, now: datetime) -> list[Listing]:
        statement = (
            select(ListingModel)
            .where(
                ListingModel.status == ListingStatus.BIDDING.value,
                ListingModel.ends_at <= now,
            )
            .order_by(ListingModel.ends_at, ListingModel.id)
        )
        models = (await self.session.scalars(statement)).all()
        return [self._to_entity(model) for model in models]

    # [AUC-04] 현재 최고 입찰로 묶여 있는 금액을 합산한다.
    async def sum_leading_bids(self, user_id: int) -> int:
        statement = select(
            func.coalesce(func.sum(ListingModel.current_bid_amount), 0)
        ).where(
            ListingModel.current_bidder_id == user_id,
            ListingModel.status == ListingStatus.BIDDING.value,
        )
        return int(await self.session.scalar(statement))

    # 매물을 등록하거나 변경한 뒤 DB에 반영한다. commit은 호출부가 담당한다.
    async def save(self, listing: Listing) -> Listing:
        values = self._to_values(listing)

        if listing.id is None:
            model = ListingModel(**values)
            self.session.add(model)
        else:
            # 기존 매물은 같은 트랜잭션에서 잠금 조회 후 변경한 엔티티여야 한다.
            model = await self.session.get(ListingModel, listing.id)
            if model is None:
                raise NotFoundError("저장할 매물을 찾을 수 없습니다.")

            for name, value in values.items():
                setattr(model, name, value)

        await self.session.flush()
        return self._to_entity(model)

    # DB에서 읽은 값을 도메인 객체로 복원한다.
    @staticmethod
    def _to_entity(model: ListingModel) -> Listing:
        return Listing(
            id=model.id,
            seller_id=model.seller_id,
            inventory_item_id=model.inventory_item_id,
            item_definition_id=model.item_definition_id,
            start_price=model.start_price,
            status=ListingStatus(model.status),
            current_bidder_id=model.current_bidder_id,
            current_bid_amount=model.current_bid_amount,
            created_at=model.created_at,
            started_at=model.started_at,
            ends_at=model.ends_at,
            closed_at=model.closed_at,
            admin_cancelled_by=model.admin_cancelled_by,
            updated_at=model.updated_at,
        )

    # 도메인 객체를 저장할 때 ORM 컬럼에 전달할 값으로 변환한다.
    @staticmethod
    def _to_values(listing: Listing) -> dict:
        return {
            "seller_id": listing.seller_id,
            "inventory_item_id": listing.inventory_item_id,
            "item_definition_id": listing.item_definition_id,
            "start_price": listing.start_price,
            "status": listing.status.value,
            "current_bidder_id": listing.current_bidder_id,
            "current_bid_amount": listing.current_bid_amount,
            "created_at": listing.created_at,
            "started_at": listing.started_at,
            "ends_at": listing.ends_at,
            "closed_at": listing.closed_at,
            "admin_cancelled_by": listing.admin_cancelled_by,
            "updated_at": listing.updated_at,
        }
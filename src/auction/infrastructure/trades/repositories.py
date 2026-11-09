# 거래 기록을 저장·조회하고 ORM 모델을 도메인 Trade로 변환한다.
# 세션은 외부에서 받으며 commit·rollback은 트랜잭션 담당자가 처리한다.
# save는 신규 거래만 저장하고 ID가 반영된 새 Trade를 반환한다.
#
# [TO DO] 정산·Trade 저장·User 제한 상태 갱신을 같은 트랜잭션으로 연결한다.
# [TO DO] 같은 사용자의 낙찰 처리를 직렬화할 잠금 계약을 합의한다.
# [TO DO] 페이지 크기와 응답 형식을 application·presentation과 맞춘다.
# [TO DO] 기간 조회 경계·중복 거래·rollback을 실제 PostgreSQL에서 테스트한다.

from dataclasses import replace
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auction.domain.trades.entities import Trade
from auction.domain.trades.repositories import TradeRepository
from auction.infrastructure.trades.models import TradeModel 


class SqlAlchemyTradeRepository(TradeRepository):
    # 같은 유스케이스에서 공유할 세션과 페이지당 조회 개수를 받는다.
    def __init__(self, session: AsyncSession, *, page_size: int):
        if page_size < 1:
            raise ValueError("페이지당 개수는 1 이상이어야 합니다.")

        self.session = session
        self.page_size = page_size

    # [AUC-05] 정산 후 신규 거래를 저장하고 ID가 채워진 새 Trade를 반환한다.
    # flush는 DB 반영 단계이며 최종 commit은 아니다.
    async def save(self, trade: Trade) -> Trade:
        if trade.id is not None:
            raise ValueError("기존 거래 기록은 수정할 수 없습니다.")

        model = TradeModel(
            listing_id=trade.listing_id,
            seller_id=trade.seller_id,
            buyer_id=trade.buyer_id,
            item_name_snapshot=trade.item_name_snapshot,
            seller_name_snapshot=trade.seller_name_snapshot,
            buyer_name_snapshot=trade.buyer_name_snapshot,
            price_snapshot=trade.price_snapshot,
            completed_at=trade.completed_at,
        )

        self.session.add(model)
        await self.session.flush()

        return replace(trade, id=model.id)

    # 매물에 연결된 거래 기록을 조회한다. 없으면 None을 반환한다.
    # 동시 중복 저장 방지는 별도로 listing_id UNIQUE 제약이 담당한다.
    async def get_by_listing(self, listing_id: int) -> Trade | None:
        statement = select(TradeModel).where(
            TradeModel.listing_id == listing_id
        )
        model = await self.session.scalar(statement)

        return self._to_entity(model) if model is not None else None

    # [AUC-07] 내 낙찰 내역을 체결 시각 최신순으로 조회한다.
    # 체결 시각이 같으면 ID 내림차순으로 정렬한다.
    async def list_by_buyer(self, buyer_id: int, page: int) -> list[Trade]:
        statement = (
            select(TradeModel)
            .where(TradeModel.buyer_id == buyer_id)
            .order_by(
                TradeModel.completed_at.desc(),
                TradeModel.id.desc(),
            )
            .offset(self._offset(page))
            .limit(self.page_size)
        )
        models = (await self.session.scalars(statement)).all()

        return [self._to_entity(model) for model in models]

    # [AUC-10] 내 판매 내역을 체결 시각 최신순으로 조회한다.
    # 결과가 없으면 빈 리스트를 반환한다.
    async def list_by_seller(self, seller_id: int, page: int) -> list[Trade]:
        statement = (
            select(TradeModel)
            .where(TradeModel.seller_id == seller_id)
            .order_by(
                TradeModel.completed_at.desc(),
                TradeModel.id.desc(),
            )
            .offset(self._offset(page))
            .limit(self.page_size)
        )
        models = (await self.session.scalars(statement)).all()

        return [self._to_entity(model) for model in models]

        # 매물·구매자·판매자 ID 조건에 맞는 거래를 페이지별로 조회한다.
    # 체결 시각 최신순으로 반환하며, 조회 결과가 없으면 빈 목록이다.
    async def list_filtered(
        self,
        page: int,
        *,
        listing_id: int | None = None,
        buyer_id: int | None = None,
        seller_id: int | None = None,
    ) -> list[Trade]:
        offset = self._offset(page)
        statement = select(TradeModel)

        # 전달된 조건만 적용하며, 여러 조건은 AND로 연결한다.
        filters = (
            (TradeModel.listing_id, listing_id),
            (TradeModel.buyer_id, buyer_id),
            (TradeModel.seller_id, seller_id),
        )
        for column, value in filters:
            if value is not None:
                statement = statement.where(column == value)

        # 같은 체결 시각에도 순서가 일정하도록 ID를 함께 정렬한다.
        statement = (
            statement
            .order_by(TradeModel.completed_at.desc(), TradeModel.id.desc())
            .offset(offset)
            .limit(self.page_size)
        )

        models = (await self.session.scalars(statement)).all()
        return [self._to_entity(model) for model in models]

    # [AUC-08] 제한 정책 계산에 필요한 기간 내 낙찰 시각 전체를 조회한다.
    # since·until은 UTC이며 양쪽 경계를 포함한다. 오래된 순으로 반환한다.
    # 같은 시각의 여러 거래도 각각 포함하고, 결과가 없으면 빈 리스트다.
    # 이번 Trade를 저장한 뒤 호출하며 반환 목록에 이번 시각을 다시 추가하지 않는다.
    async def find_win_times_between(
        self,
        buyer_id: int,
        since: datetime,
        until: datetime,
    ) -> list[datetime]:
        if since > until:
            raise ValueError("조회 시작 시각은 종료 시각보다 늦을 수 없습니다.")

        statement = (
            select(TradeModel.completed_at)
            .where(
                TradeModel.buyer_id == buyer_id,
                TradeModel.completed_at >= since,
                TradeModel.completed_at <= until,
            )
            .order_by(
                TradeModel.completed_at,
                TradeModel.id,
            )
        )

        return list((await self.session.scalars(statement)).all())

    # 기존 계약: 최근 낙찰 시각을 최신순으로 최대 limit개 조회한다.
    # B 방식 집계에는 find_win_times_between을 사용한다.
    # [TO DO] 사용처 확인 후 도메인 인터페이스와 함께 제거 여부를 결정한다.
    async def recent_win_times(
        self,
        buyer_id: int,
        limit: int,
    ) -> list[datetime]:
        if limit < 1:
            raise ValueError("조회 개수는 1 이상이어야 합니다.")

        statement = (
            select(TradeModel.completed_at)
            .where(TradeModel.buyer_id == buyer_id)
            .order_by(
                TradeModel.completed_at.desc(),
                TradeModel.id.desc(),
            )
            .limit(limit)
        )

        return list((await self.session.scalars(statement)).all())

    # 1부터 시작하는 페이지 번호를 DB 조회 시작 위치로 변환한다.
    def _offset(self, page: int) -> int:
        if page < 1:
            raise ValueError("페이지 번호는 1 이상이어야 합니다.")

        return (page - 1) * self.page_size

    # 저장된 값을 복원한다. 신규 거래 생성 규칙을 다시 실행하지 않는다.
    @staticmethod
    def _to_entity(model: TradeModel) -> Trade:
        return Trade(
            id=model.id,
            listing_id=model.listing_id,
            seller_id=model.seller_id,
            buyer_id=model.buyer_id,
            item_name_snapshot=model.item_name_snapshot,
            seller_name_snapshot=model.seller_name_snapshot,
            buyer_name_snapshot=model.buyer_name_snapshot,
            price_snapshot=model.price_snapshot,
            completed_at=model.completed_at,
        )
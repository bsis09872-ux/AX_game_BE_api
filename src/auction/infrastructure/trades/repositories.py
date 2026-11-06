# 거래 Repository의 SQLAlchemy 구현체다.
# domain 인터페이스를 구현하며 ORM 모델과 불변 Trade 엔티티를 변환한다.
# DB 세션은 외부에서 받으며 commit·rollback은 트랜잭션 담당자가 처리한다.
#
# 사용 계약:
# - save는 신규 거래만 저장하며 기존 거래의 수정은 제공하지 않는다.
# - 저장 후 ID가 반영된 새 Trade를 반환하므로 반환값을 사용한다.
# - 매물당 거래 1건은 DB의 listing_id UNIQUE 제약으로 보장한다.
# - 정산·매물 상태 변경·거래 저장은 하나의 트랜잭션으로 처리한다.
# - 조회 결과가 없어도 목록은 빈 리스트로 반환한다.
#
# 확인할 것:
# [ ] 페이지 번호는 1부터, 내역은 체결 시각 최신순으로 팀과 합의
# [ ] page_size를 외부 설정에서 전달
# [ ] 중복 거래 저장 시 rollback과 업무 오류 변환 확인
# [ ] 실제 PostgreSQL에서 저장·조회·정산 rollback 테스트

from abc import ABC
from dataclasses import replace
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auction.domain.trades.entities import Trade
from auction.domain.trades.repositories import TradeRepository
from auction.infrastructure.trades.models import TradeModel


class SqlAlchemyTradeRepository(TradeRepository):
    def __init__(self, session: AsyncSession, *, page_size: int):
        if page_size < 1:
            raise ValueError("페이지당 개수는 1 이상이어야 합니다.")

        self.session = session
        self.page_size = page_size

    # [AUC-05] 정산 후 만든 신규 거래를 저장하고 ID가 반영된 기록을 반환한다.
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

    # 매물에 연결된 거래 기록이 필요할 때 조회한다.
    async def get_by_listing(self, listing_id: int) -> Trade | None:
        statement = select(TradeModel).where(
            TradeModel.listing_id == listing_id
        )
        model = await self.session.scalar(statement)
        return self._to_entity(model) if model is not None else None

    # [AUC-07] 내 낙찰 내역을 체결 시각 최신순으로 조회한다.
    async def list_by_buyer(self, buyer_id: int, page: int) -> list[Trade]:
        statement = (
            select(TradeModel)
            .where(TradeModel.buyer_id == buyer_id)
            .order_by(TradeModel.completed_at.desc(), TradeModel.id.desc())
            .offset(self._offset(page))
            .limit(self.page_size)
        )
        models = (await self.session.scalars(statement)).all()
        return [self._to_entity(model) for model in models]

    # [AUC-10] 내 판매 내역을 체결 시각 최신순으로 조회한다.
    async def list_by_seller(self, seller_id: int, page: int) -> list[Trade]:
        statement = (
            select(TradeModel)
            .where(TradeModel.seller_id == seller_id)
            .order_by(TradeModel.completed_at.desc(), TradeModel.id.desc())
            .offset(self._offset(page))
            .limit(self.page_size)
        )
        models = (await self.session.scalars(statement)).all()
        return [self._to_entity(model) for model in models]

    # [AUC-08] 새 입찰 제한 판단에 필요한 최근 낙찰 시각만 조회한다.
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
            .order_by(TradeModel.completed_at.desc(), TradeModel.id.desc())
            .limit(limit)
        )
        return list((await self.session.scalars(statement)).all())

    # 페이지 조회를 시작할 위치를 계산한다.
    def _offset(self, page: int) -> int:
        if page < 1:
            raise ValueError("페이지 번호는 1 이상이어야 합니다.")

        return (page - 1) * self.page_size

    # DB에서 읽은 거래 기록을 불변 도메인 객체로 복원한다.
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
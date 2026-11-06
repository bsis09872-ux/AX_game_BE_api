"""SQLAlchemy 지갑 저장소

세션은 주입받아 공유하고 commit하지 않는다.
"""
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from wallet.domain.exceptions import WalletNotFoundError
from wallet.domain.repository import WalletRepository
from wallet.domain.wallet import Balance, Wallet
from wallet.infrastructure.external_tables import listings
from wallet.infrastructure.models import WalletModel


def _to_wallet(model: WalletModel) -> Wallet:
    # DB의 int 잔액을 도메인 값 객체 Balance로 감싼다
    return Wallet(
        user_id=model.user_id,
        balance=Balance(model.balance),
        updated_at=model.updated_at,
    )


class SqlAlchemyWalletRepository(WalletRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: int) -> Wallet | None:
        model = await self.session.scalar(
            select(WalletModel).where(WalletModel.user_id == user_id)
        )
        return None if model is None else _to_wallet(model)

    async def save(self, user_id: int, balance: int) -> Wallet:
        """잔액을 덮어쓰고 갱신된 지갑을 돌려준다. 지갑이 없으면 WalletNotFoundError.

        balance < 0 이면 DB CHECK(ck_wallets_balance_non_negative) 위반으로 flush 시점에 실패한다.
        """
        model = await self.session.scalar(
            update(WalletModel)
            .where(WalletModel.user_id == user_id)
            .values(balance=balance, updated_at=func.now())
            .returning(WalletModel)
            # 세션에 이미 올라온 WalletModel도 갱신된 값으로 다시 채운다
            .execution_options(populate_existing=True)
        )
        if model is None:
            raise WalletNotFoundError()
        return _to_wallet(model)

    async def held_amount(self, user_id: int) -> int:
        statement = select(func.coalesce(func.sum(listings.c.current_bid_amount), 0)).where(
            listings.c.current_bidder_id == user_id,
            listings.c.status == "BIDDING",  # 마감이 지나도 정산 전이면 BIDDING이라 포함된다
        )
        return int(await self.session.scalar(statement))


# from datetime import datetime

# from sqlalchemy import Select, func, insert, or_, select, update
# from sqlalchemy.ext.asyncio import AsyncSession

# from wallet.domain.wallet import TradeRecord, Wallet
# from wallet.domain.repository import RoleFilter, WalletRepository
# from wallet.infrastructure.external_tables import item_definitions, listings, trades, users
# from wallet.infrastructure.models import WalletModel


# def _to_wallet(model: WalletModel) -> Wallet:
#     return Wallet(user_id=model.user_id, balance=model.balance, updated_at=model.updated_at)


# # trades + listings.seller_id 조인 (trades에 판매자 ID가 없으므로)
# _TRADE_COLUMNS = (
#     trades.c.id,
#     trades.c.listing_id,
#     trades.c.buyer_id,
#     listings.c.seller_id,
#     trades.c.item_name_snapshot,
#     trades.c.seller_name_snapshot,
#     trades.c.buyer_name_snapshot,
#     trades.c.price_snapshot,
#     trades.c.completed_at,
# )
# _TRADE_JOIN = trades.join(listings, listings.c.id == trades.c.listing_id)


# def _to_trade(row) -> TradeRecord:
#     return TradeRecord(
#         trade_id=row.id,
#         listing_id=row.listing_id,
#         buyer_id=row.buyer_id,
#         seller_id=row.seller_id,
#         item_name=row.item_name_snapshot,
#         seller_name=row.seller_name_snapshot,
#         buyer_name=row.buyer_name_snapshot,
#         price=row.price_snapshot,
#         completed_at=row.completed_at,
#     )


# class SqlAlchemyWalletRepository(WalletRepository):
#     def __init__(self, session: AsyncSession):
#         self.session = session

#     # ---------- wallets ----------
#     async def get(self, user_id: int) -> Wallet | None:
#         model = await self.session.get(WalletModel, user_id)
#         return None if model is None else _to_wallet(model)

#     async def lock(self, user_ids: list[int]) -> dict[int, Wallet]:
#         statement = (
#             select(WalletModel)
#             .where(WalletModel.user_id.in_(user_ids))
#             .order_by(WalletModel.user_id)
#             .with_for_update()
#             # 이미 세션에 올라온 객체도 잠근 시점의 값으로 다시 읽는다
#             .execution_options(populate_existing=True)
#         )
#         result = await self.session.execute(statement)
#         return {m.user_id: _to_wallet(m) for m in result.scalars()}

#     async def create(self, user_id: int, balance: int) -> Wallet:
#         model = WalletModel(user_id=user_id, balance=balance)
#         self.session.add(model)
#         await self.session.flush()  # 같은 계정 지갑이 있으면 여기서 UNIQUE(PK) 위반
#         await self.session.refresh(model)  # server_default인 updated_at 읽기
#         return _to_wallet(model)

#     async def set_balance(self, user_id: int, balance: int) -> None:
#         await self.session.execute(
#             update(WalletModel)
#             .where(WalletModel.user_id == user_id)
#             .values(balance=balance, updated_at=func.now())
#             # 세션에 올라온 WalletModel이 있으면 다음 조회 때 다시 읽게 한다
#             .execution_options(synchronize_session="fetch")
#         )

#     # ---------- 다른 도메인 테이블 조회 ----------
#     async def held_amount(self, user_id: int) -> int:
#         statement = select(func.coalesce(func.sum(listings.c.current_bid_amount), 0)).where(
#             listings.c.current_bidder_id == user_id,
#             listings.c.status == "BIDDING",  # 마감이 지나도 정산 전이면 BIDDING이라 포함된다
#         )
#         return int(await self.session.scalar(statement))

#     async def display_names(self, user_ids: list[int]) -> dict[int, str]:
#         result = await self.session.execute(
#             select(users.c.id, users.c.display_name).where(users.c.id.in_(user_ids))
#         )
#         return {row.id: row.display_name for row in result}

#     async def item_name(self, item_definition_id: int) -> str | None:
#         return await self.session.scalar(
#             select(item_definitions.c.name).where(item_definitions.c.id == item_definition_id)
#         )

#     # ---------- trades ----------
#     @staticmethod
#     def _role_condition(user_id: int, role: RoleFilter):
#         as_buyer = trades.c.buyer_id == user_id
#         as_seller = listings.c.seller_id == user_id
#         if role == "buy":
#             return as_buyer
#         if role == "sell":
#             return as_seller
#         return or_(as_buyer, as_seller)

#     async def list_trades(
#         self, user_id: int, role: RoleFilter, offset: int, limit: int
#     ) -> tuple[list[TradeRecord], int]:
#         condition = self._role_condition(user_id, role)

#         page: Select = (
#             select(*_TRADE_COLUMNS)
#             .select_from(_TRADE_JOIN)
#             .where(condition)
#             .order_by(trades.c.completed_at.desc(), trades.c.id.desc())
#             .offset(offset)
#             .limit(limit)
#         )
#         total = select(func.count()).select_from(_TRADE_JOIN).where(condition)

#         rows = (await self.session.execute(page)).all()
#         count = await self.session.scalar(total)
#         return [_to_trade(r) for r in rows], int(count)

#     async def get_trade(self, trade_id: int) -> TradeRecord | None:
#         row = (
#             await self.session.execute(
#                 select(*_TRADE_COLUMNS).select_from(_TRADE_JOIN).where(trades.c.id == trade_id)
#             )
#         ).first()
#         return None if row is None else _to_trade(row)

#     async def insert_trade(
#         self,
#         *,
#         listing_id: int,
#         buyer_id: int,
#         item_name: str,
#         seller_name: str,
#         buyer_name: str,
#         price: int,
#         completed_at: datetime,
#     ) -> int:
#         statement = (
#             insert(trades)
#             .values(
#                 listing_id=listing_id,
#                 buyer_id=buyer_id,
#                 item_name_snapshot=item_name,
#                 seller_name_snapshot=seller_name,
#                 buyer_name_snapshot=buyer_name,
#                 price_snapshot=price,
#                 completed_at=completed_at,
#             )
#             .returning(trades.c.id)
#         )
#         return int(await self.session.scalar(statement))

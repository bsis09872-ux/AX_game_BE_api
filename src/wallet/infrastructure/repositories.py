"""SQLAlchemy 지갑 저장소 (wallets 테이블만 다룬다)

세션은 주입받아 공유하고 commit하지 않는다.
예약 금액은 경매가 제공하는 HeldAmountReader로 받는다 (wiring에서 주입).
"""
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from wallet.domain.exceptions import WalletNotFoundError
from wallet.domain.repository import WalletRepository
from wallet.domain.wallet import Balance, Wallet
from wallet.infrastructure.models import WalletModel

# PostgreSQL 외래키 위반 SQLSTATE
_FK_VIOLATION = "23503"


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

    async def create(self, user_id: int, balance: int) -> Wallet:
        model = WalletModel(user_id=user_id, balance=balance)
        self.session.add(model)
        await self.session.flush()  # 같은 계정 지갑이 있으면 여기서 PK 위반
        await self.session.refresh(model)  # server_default인 updated_at 읽기
        return _to_wallet(model)

    async def create_if_absent(self, user_id: int, balance: int) -> Wallet | None:
        # ON CONFLICT DO NOTHING: 동시에 처음 접근해도 지갑은 하나만 생기고, 늦은 쪽은 None을 받는다
        statement = (
            pg_insert(WalletModel)
            .values(user_id=user_id, balance=balance)
            .on_conflict_do_nothing(index_elements=[WalletModel.user_id])
            .returning(WalletModel)
        )
        try:
            model = await self.session.scalar(statement)
        except IntegrityError as exc:
            # users에 없는 회원이면 지갑도 없다(404). users 서비스에 묻지 않고 DB FK로 판단한다.
            if getattr(exc.orig.__cause__, "sqlstate", None) == _FK_VIOLATION:
                raise WalletNotFoundError() from exc
            raise
        return None if model is None else _to_wallet(model)

    async def lock(self, user_ids: list[int]) -> dict[int, Wallet]:
        result = await self.session.execute(
            select(WalletModel)
            .where(WalletModel.user_id.in_(user_ids))
            .order_by(WalletModel.user_id)
            .with_for_update()
            # 이미 세션에 올라온 객체도 잠근 시점의 값으로 다시 읽는다
            .execution_options(populate_existing=True)
        )
        return {m.user_id: _to_wallet(m) for m in result.scalars()}

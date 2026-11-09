# 트랜잭션 Adapter: 경매의 TransactionManager 계약을 SQLAlchemy 세션에 연결한다.
# 세션은 호출자가 만들고 닫는다. Repository·Adapter와 같은 세션을 받아야 한 트랜잭션으로 묶인다.
# 요청 처리 중 오류의 rollback은 팀 공통 get_db가 한다.
# rollback은 여러 매물을 하나씩 처리하다 한 건만 되돌릴 때 쓴다.

from sqlalchemy.ext.asyncio import AsyncSession

from auction.application.contract import TransactionManager


class SqlAlchemyTransactionManager(TransactionManager):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

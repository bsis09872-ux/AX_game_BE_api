"""commit 어댑터: UnitOfWork 계약을 SQLAlchemy 세션의 commit에 연결한다

- 서비스가 "확정해 달라"고 부탁하면 세션의 commit을 부른다
- rollback은 하지 않는다 (오류 때 rollback은 팀 공통 get_db가 한다)
- 세션은 호출자가 만들고 닫는다
"""

from sqlalchemy.ext.asyncio import AsyncSession
from inventory.application.contracts import UnitOfWork

class SqlAlchemyUnitOfWork(UnitOfWork):
    
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()
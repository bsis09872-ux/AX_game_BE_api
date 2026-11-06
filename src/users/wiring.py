# 회원 서비스와 SQLAlchemy 저장소를 연결한다.
from sqlalchemy.ext.asyncio import AsyncSession

from users.application.service import UserService
from users.infrastructure.repositories import SqlAlchemyUserRepository


def build_user_service(session: AsyncSession) -> UserService:
    # 요청의 세션을 공유하며, 세션 종료는 호출자가 담당한다.
    repository = SqlAlchemyUserRepository(session=session)
    return UserService(repository=repository)

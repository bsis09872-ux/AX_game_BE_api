# 요청별 DB 세션을 회원 저장소, 토큰 폐기 저장소와 트랜잭션에 공유한다.
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from auth.application.service import AuthService
from auth.infrastructure.password_hasher import PasslibPasswordHasher
from auth.infrastructure.repositories import SqlAlchemyRevokedTokenRepository
from auth.infrastructure.token_codec import get_token_codec
from auth.infrastructure.user_creator import UserCreatorAdapter
from auth.infrastructure.user_reader import UserReaderAdapter
from users.wiring import build_user_service


@lru_cache
def get_password_hasher() -> PasslibPasswordHasher:
    return PasslibPasswordHasher()


def build_auth_service(session: AsyncSession) -> AuthService:
    user_service = build_user_service(session)
    return AuthService(
        password_hasher=get_password_hasher(),
        user_creator=UserCreatorAdapter(user_service),
        user_reader=UserReaderAdapter(user_service),
        token_codec=get_token_codec(),
        revoked_tokens=SqlAlchemyRevokedTokenRepository(session),
        transaction=session,
    )

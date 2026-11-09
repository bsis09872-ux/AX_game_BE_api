# 요청별 DB 세션을 회원 저장소, 로그인 세션 저장소와 트랜잭션에 공유한다.
from functools import lru_cache
import os

from sqlalchemy.ext.asyncio import AsyncSession

from auth.application.service import AuthService
from auth.infrastructure.password_hasher import PasslibPasswordHasher
from auth.infrastructure.token_codec import get_token_codec
from auth.infrastructure.user_creator import UserCreatorAdapter
from auth.infrastructure.user_reader import UserReaderAdapter
from users.wiring import build_user_service
from auth.infrastructure.refresh_token_codec import OpaqueRefreshTokenCodec
from auth.infrastructure.session_repository import SqlAlchemySessionRepository
from auth.infrastructure.revoked_session_cache import RevokedSessionCache
from users.application.admin_service import MemberAdminService


def build_member_admin_service(session: AsyncSession) -> MemberAdminService:
    return MemberAdminService(build_user_service(session), get_password_hasher(), session,
                              SqlAlchemySessionRepository(session))


@lru_cache
def get_revoked_session_cache() -> RevokedSessionCache:
    return RevokedSessionCache()


def initialize_auth() -> None:
    get_token_codec()
    get_refresh_ttl_seconds()


def get_refresh_ttl_seconds() -> int:
    ttl = int(os.environ.get("REFRESH_TTL_SECONDS", "604800"))
    if not 30 <= ttl <= 2592000:
        raise ValueError("REFRESH_TTL_SECONDS는 30~2592000 사이여야 합니다.")
    return ttl


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
        transaction=session,
        sessions=SqlAlchemySessionRepository(session),
        refresh_codec=OpaqueRefreshTokenCodec(),
        refresh_ttl_seconds=get_refresh_ttl_seconds(),
        revoked_sessions=get_revoked_session_cache(),
    )

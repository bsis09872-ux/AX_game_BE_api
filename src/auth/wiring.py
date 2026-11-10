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
from auth.application.admin_contracts import AdminAuctionReader
from auth.infrastructure.admin_auction_reader import AdminAuctionReaderAdapter


def build_admin_auction_reader(session: AsyncSession) -> AdminAuctionReader:
    # inventory.wiring도 인증 조립부를 사용하므로 요청 시점에 가져와 순환 import를 피한다.
    from auction.wiring import build_listing_service, build_trade_service

    # 경매 도메인이 공개한 조립부를 사용하고, 관리자 화면에는 조회 계약만 노출한다.
    return AdminAuctionReaderAdapter(
        build_listing_service(session),
        build_trade_service(session),
    )


def build_member_admin_service(session: AsyncSession) -> MemberAdminService:
    # TODO(지갑 연동): users.application.contracts.MemberWalletProvisioner 구현이 반영되면
    # 같은 session으로 주입한다. 회원 flush -> create_wallet -> 마지막 한 번 commit,
    # 초기 지급 로그 확정은 commit 성공 후 연결한다. 지금은 회원 계정만 생성한다.
    # 기존 회원의 지갑 누락 보정 정책은 지갑 담당과 별도로 합의해야 한다.
    # TODO(지갑 담당): PR #21의 최초 사용 시 생성 정책과 위 생성 계약을 맞춘다.
    # 최초 사용 시 생성이 확정되면 MemberWalletProvisioner와 회원 생성 연동 TODO를 제거한다.
    return MemberAdminService(build_user_service(session), get_password_hasher(), session,
                              SqlAlchemySessionRepository(session))


# TODO(인벤토리/앱 조립 담당): PR #25의 main.py 등록을 병합 후 확인한다.
# create_inventory_web_router에는 get_current_web_user_id를 주입하고,
# fishing_router는 is_fishing_enabled()에 따라 /v1에 등록한다.
# 관리자 회원 보유 아이템 조회는 별도로 연결되어 있으며 일반 사용자 라우터를 대체하지 않는다.


@lru_cache
def get_revoked_session_cache() -> RevokedSessionCache:
    return RevokedSessionCache()


def initialize_auth() -> None:
    get_token_codec()
    get_refresh_ttl_seconds()


def get_refresh_ttl_seconds() -> int:
    ttl = int(os.environ.get("REFRESH_TTL_SECONDS", "1800"))
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

# 회원 서비스와 SQLAlchemy 저장소를 연결한다.
from sqlalchemy.ext.asyncio import AsyncSession

from users.application.admin_contracts import PasswordHasher, SessionRevoker
from users.application.admin_service import MemberAdminService
from users.application.contracts import AdminRoleChecker
from users.application.service import UserService
from users.infrastructure.repositories import SqlAlchemyUserRepository


def build_user_service(session: AsyncSession) -> UserService:
    # TODO(경매 연동): application.contracts.AuctionMemberGateway를 경매 어댑터에 연결한다.
    # 입찰 허용 검사는 effective_auction_blocked_until, 자동 제한 정책 계산은
    # auction_blocked_until을 사용한다. 매물 -> 아이템 -> 회원 -> 지갑 잠금 순서와
    # 동일 세션을 유지한다. 현재 이 wiring만으로 실제 입찰 차단이 연결된 것은 아니다.
    # 요청의 세션을 공유하며, 세션 종료는 호출자가 담당한다.
    repository = SqlAlchemyUserRepository(session=session)
    return UserService(repository=repository)


def build_admin_role_checker(session: AsyncSession) -> AdminRoleChecker:
    # 호출 도메인의 요청 세션을 공유한다. 인증된 회원 ID는 auth에서 전달받는다.
    # TODO(지갑 담당): 충전 권한 검사 계약에 이 checker를 연결한다. 없는 회원도 False이며
    # USER, 탈퇴, 로그인 정지 회원은 거절하고 DB 조회 실패는 예외로 전달한다.
    return build_user_service(session)


def build_member_admin_service(
    session: AsyncSession, *, passwords: PasswordHasher, sessions: SessionRevoker,
) -> MemberAdminService:
    # 인증 구현은 앱 조립부에서 주입한다. Users는 Auth를 import하지 않는다.
    return MemberAdminService(
        users=build_user_service(session), passwords=passwords,
        transaction=session, sessions=sessions,
    )

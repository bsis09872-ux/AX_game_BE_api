"""앱에서 사용할 도메인 서비스를 조립한다. 업무 규칙은 각 도메인이 소유한다."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from auth.wiring import build_session_revoker, get_password_hasher
from auction.application.admin_queries import AdminAuctionQueries
from auction.wiring import build_admin_auction_queries
from users.application.admin_service import MemberAdminService
from users.wiring import build_member_admin_service


def get_member_admin_service(session: AsyncSession = Depends(get_db)) -> MemberAdminService:
    # 같은 요청 세션을 사용해 회원 정지와 인증 세션 폐기를 함께 확정한다.
    return build_member_admin_service(
        session, passwords=get_password_hasher(), sessions=build_session_revoker(session),
    )


def get_admin_auction_queries(session: AsyncSession = Depends(get_db)) -> AdminAuctionQueries:
    return build_admin_auction_queries(session)

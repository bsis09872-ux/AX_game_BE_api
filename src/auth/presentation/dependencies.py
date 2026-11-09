# 인증 라우터에 요청 세션으로 구성한 AuthService를 제공한다.
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db

from auth.application.service import AuthService
from auth.wiring import build_auth_service
from auth.wiring import build_member_admin_service
from users.application.admin_service import MemberAdminService
from auth.application.dto import TokenClaims
from auth.domain.exceptions import AuthenticationError
from shared.core.exceptions import ForbiddenError
from users.application.dto import UserSummary
from users.application.service import UserService
from users.presentation.dependencies import get_user_service
from users.domain.exceptions import UserNotFoundError


# 애플리케이션 기준 상대 URL로 Swagger의 토큰 발급 경로를 지정한다.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="v1/auth/token", auto_error=False)

def get_auth_service(session: AsyncSession = Depends(get_db)) -> AuthService:
    # 세션 수명과 예외 발생 시 rollback은 get_db가 담당한다.
    return build_auth_service(session=session)


def get_member_admin_service(session: AsyncSession = Depends(get_db)) -> MemberAdminService:
    return build_member_admin_service(session)


def get_bearer_token(token: str | None = Depends(oauth2_scheme)) -> str:
    if not token:
        raise AuthenticationError()
    return token


async def get_current_token(
    token: str = Depends(get_bearer_token),
    service: AuthService = Depends(get_auth_service),
) -> TokenClaims:
    # 서명, 만료, 폐기 여부와 현재 회원 상태를 모두 확인한다.
    return await service.authenticate(token)


async def get_current_user_id(
    claims: TokenClaims = Depends(get_current_token),
) -> int:
    return claims.user_id


async def get_current_user(
    user_id: int = Depends(get_current_user_id),
    users: UserService = Depends(get_user_service),
) -> UserSummary:
    try:
        user = await users.get_user_summary(user_id)
    except UserNotFoundError as exc:
        raise AuthenticationError() from exc
    if not user.is_active:
        raise AuthenticationError()
    return user


async def require_admin(user: UserSummary = Depends(get_current_user)) -> UserSummary:
    if user.role != "ADMIN":
        raise ForbiddenError()
    return user

"""의존성 주입(Depends) 함수

- 라우터가 필요로 하는 서비스와 DB 세션을 밖에서 만들어 넘겨 주는 곳이다
- 현재 사용자 확인은 CurrentUserAdapter가 한다: 토큰은 auth의 AuthService로 확인하고, 역할(role)은 users의 회원 정보(UserSummary.role)에서 가져온다 (다른 도메인의 infrastructure는 직접 import하지 않고 wiring을 거친다)
- 관리자 확인은 require_admin 의존성으로 한다
- 업무 규칙을 두지 않는다
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db

from inventory.application.contracts import CurrentUserProvider, CurrentUser
from inventory.application.service import InventoryService
from inventory.application.fishing_service import FishingService

from inventory.wiring import (
    build_current_user_provider,
    build_fishing_service,
    build_inventory_service,
)

from shared.core.exceptions import ForbiddenError


# 헤더가 없어도 자동 오류를 내지 않고 None 반환 (팀 규칙)
_bearer = HTTPBearer(auto_error=False)


# 서비스 조립
def get_inventory_service(session: AsyncSession = Depends(get_db)) -> InventoryService:
    return build_inventory_service(session)


# 토큰 확인
def get_current_user_provider(session: AsyncSession = Depends(get_db)) -> CurrentUserProvider:
    return build_current_user_provider(session)


# 401 응답 
def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={'code': 'UNAUTHORIZED', 'message': '로그인이 필요하거나 토큰이 유효하지 않습니다.'},
        headers={'WWW-Authenticate': 'Bearer'}
    )


# 요청자 확인
async def get_current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
        provider: CurrentUserProvider = Depends(get_current_user_provider)
) -> CurrentUser:

    # 헤더가 없거나 Bearer 방식이 아니면 credentials가 None
    if credentials is None:
        raise _unauthorized()
    user = await provider.authenticate(credentials.credentials)
    
    # 토큰이 틀렸거나 만료
    if user is None:
        raise _unauthorized()
    return user


# 관리자 확인
# 로그인은 get_current_user가 확인하고 여기서는 역할만 확인
async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != 'ADMIN':
        raise ForbiddenError()
    return user


# 낚시 서비스
def get_fishing_service(session: AsyncSession = Depends(get_db)) -> FishingService:
    return build_fishing_service(session)
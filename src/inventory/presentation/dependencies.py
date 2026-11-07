"""의존성 주입(Depends) 함수

- 라우터가 필요로 하는 서비스와 DB 세션을 밖에서 만들어 넘겨 주는 곳이다
- 현재 사용자 확인(인증)은 인증 담당이 제공하는 의존성을 가져다 쓴다 (직접 구현하지 않는다)
- 관리자 확인은 require_admin 의존성으로 한다
- 업무 규칙을 두지 않는다
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from inventory.application.contracts import CurrentUserProvider, CurrentUser
from inventory.application.service import InventoryService
from inventory.wiring import build_current_user_provider, build_inventory_service

# 헤더가 없어도 자동 오류를 내지 않고 None 반환 (팀 규칙)
_bearer = HTTPBearer(auto_error=False)

# 서비스 조립
def get_inventory_service(session: AsyncSession = Depends(get_db)) -> InventoryService:
    return build_inventory_service(session)

# 토근 확인
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
# 인증 라우터에 요청 세션으로 구성한 AuthService를 제공한다.
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db

from auth.application.service import AuthService
from auth.wiring import build_auth_service
from auth.application.contracts import TokenClaims
from auth.domain.exceptions import AuthenticationError


# 애플리케이션 기준 상대 URL로 Swagger의 토큰 발급 경로를 지정한다.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="v1/auth/token", auto_error=False)

def get_auth_service(session: AsyncSession = Depends(get_db)) -> AuthService:
    # 세션 수명과 예외 발생 시 rollback은 get_db가 담당한다.
    return build_auth_service(session=session)


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

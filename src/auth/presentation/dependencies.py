"""인증 의존성 (임시)

TODO(auth 담당): 폐기 토큰(revoked_tokens)·탈퇴 회원 검사, 설정 관리로 시크릿 이동.
지금은 다른 도메인 라우터가 import할 수 있도록 Access Token의 sub만 꺼낸다.
"""
import os
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"

# auto_error=False: 토큰 누락도 아래에서 같은 401 형식으로 응답한다
bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail={"code": "UNAUTHORIZED", "message": "인증이 필요합니다."},
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> int:
    if credentials is None:
        raise _UNAUTHORIZED
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _UNAUTHORIZED

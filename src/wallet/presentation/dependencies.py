"""인증 의존성 (wallet 임시본)

auth 도메인에 현재 사용자 ID 의존성이 아직 없어 wallet 안에 임시로 둔다.
TODO: auth에 get_current_user_id(폐기 토큰·탈퇴 회원 검사 포함)가 생기면
      router.py의 import를 auth 쪽으로 바꾸고 이 파일을 삭제한다.
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

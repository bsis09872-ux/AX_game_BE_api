# 인증 라우터에 요청 세션으로 구성한 AuthService를 제공한다.
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db

from auth.application.service import AuthService
from auth.wiring import build_auth_service

def get_auth_service(session: AsyncSession = Depends(get_db)) -> AuthService:
    # 세션 수명과 예외 발생 시 rollback은 get_db가 담당한다.
    return build_auth_service(session=session)

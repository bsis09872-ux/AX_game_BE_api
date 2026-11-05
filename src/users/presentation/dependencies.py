# 회원 라우터에 요청별 UserService를 제공한다.
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from users.application.service import UserService
from users.wiring import build_user_service


def get_user_service(session: AsyncSession = Depends(get_db)) -> UserService:
    # 같은 요청에서는 세션을 공유하고, 종료 처리는 get_db에 맡긴다.
    return build_user_service(session=session)

# 지갑 라우터에 요청 세션으로 구성한 WalletService를 제공한다.
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from users.application.service import UserService
from users.presentation.dependencies import get_user_service
from wallet.application.service import WalletService
from wallet.wiring import build_wallet_service


async def get_actor_role(
    user_id: Annotated[int, Depends(get_current_user_id)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> str:
    # 요청한 사용자의 role('USER' | 'ADMIN')을 users에서 읽는다. RoleCheckImpl이 이 값으로 판단한다.
    user = await user_service.get_user(user_id)
    return user.role


def get_wallet_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    actor_role: Annotated[str, Depends(get_actor_role)],
) -> WalletService:
    # 세션 수명과 예외 발생 시 rollback은 get_db가 담당한다.
    return build_wallet_service(session=session, actor_role=actor_role)

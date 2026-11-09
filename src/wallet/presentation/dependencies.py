# 지갑 라우터에 요청 세션으로 조립한 WalletService를 제공한다.
#
# presentation은 다른 도메인(auth, users)을 import하지 않는다.
#   - 인증된 사용자 ID: main.py가 create_wallet_router(get_current_user_id)로 주입한다.
#   - 관리자 여부 판단: 서비스의 RoleCheck가 하고, 구현체 조립은 wiring이 한다.
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from wallet.application.service import WalletService
from wallet.wiring import build_wallet_service

# 같은 요청 안에서는 auth·users·wallet이 모두 이 세션 하나를 공유한다(FastAPI 의존성 캐시)
SessionDep = Annotated[AsyncSession, Depends(get_db)]


def get_wallet_service(session: SessionDep) -> WalletService:
    # 세션 수명과 예외 발생 시 rollback은 get_db가 담당한다.
    return build_wallet_service(session=session)

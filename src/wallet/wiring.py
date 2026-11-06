# 지갑 서비스와 인프라 구현체를 연결한다.
# 다른 도메인(auth 가입, auction 입찰·정산)도 이 함수로 같은 세션의 WalletService를 얻는다.
from sqlalchemy.ext.asyncio import AsyncSession

from wallet.application.service import WalletService
from wallet.infrastructure.balance_recoder import BalanceRecordImpl
from wallet.infrastructure.repositories import SqlAlchemyWalletRepository
from wallet.infrastructure.role_checker import RoleCheckImpl


def build_wallet_service(session: AsyncSession, actor_role: str | None = None) -> WalletService:
    # 호출자의 세션을 공유하며, 세션 종료와 commit은 호출자가 담당한다.
    # commit 성공 뒤 service.logger.flush()로 잔액 변경 로그를 남긴다.
    return WalletService(
        roleCheck=RoleCheckImpl(actor_role),
        logger=BalanceRecordImpl(),
        wallet_repo=SqlAlchemyWalletRepository(session=session),
    )

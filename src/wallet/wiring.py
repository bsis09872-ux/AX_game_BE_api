# 지갑 서비스에 infrastructure 구현체를 연결한다 (조립 지점, composition root).
#
# 의존 방향: presentation → application → domain ← infrastructure, 그리고 wiring이 전부를 조립한다.
#   - domain·application은 계약(ABC)만 알고 구현체를 import하지 않는다.
#   - 다른 도메인(users)을 조립하는 곳은 여기뿐이다.
# 라우터(presentation)와 다른 도메인(auction 입찰·정산)도 이 함수로 같은 세션의 WalletService를 얻는다.
from sqlalchemy.ext.asyncio import AsyncSession

from users.wiring import build_user_service
from wallet.application.service import WalletService
from wallet.infrastructure.balance_recoder import BalanceRecordImpl
from wallet.infrastructure.repositories import SqlAlchemyWalletRepository
from wallet.infrastructure.role_checker import UserRoleCheck


def build_wallet_service(session: AsyncSession) -> WalletService:
    # 호출자의 세션을 공유하며, 세션 종료와 commit은 호출자가 담당한다.
    # commit 성공 뒤 service.logger.flush(), 실패 시 service.logger.discard()로 잔액 변경 로그를 처리한다.
    # UserRoleCheck는 is_admin()이 불릴 때(관리자 충전)만 users를 조회하므로 조회·입찰·정산에는 비용이 없다.
    return WalletService(
        roleCheck=UserRoleCheck(build_user_service(session)),
        logger=BalanceRecordImpl(),
        wallet_repo=SqlAlchemyWalletRepository(session=session),
    )

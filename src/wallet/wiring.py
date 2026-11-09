# 지갑 서비스에 infrastructure 구현체를 연결한다 (조립 지점, composition root).
#
# 의존 방향: presentation → application → domain ← infrastructure, 그리고 wiring이 전부를 조립한다.
#   - domain·application은 계약(domain의 ABC, application/contracts.py의 Protocol)만 알고 구현체를 import하지 않는다.
#   - 다른 도메인은 그 도메인의 wiring으로만 가져온다 (users: 관리자 확인).
# 라우터(presentation)와 다른 도메인(auction 입찰·정산)도 이 함수로 같은 세션의 WalletService를 얻는다.
from sqlalchemy.ext.asyncio import AsyncSession

from users.wiring import build_admin_role_checker
from wallet.application.contracts import HeldAmountReader
from wallet.application.service import WalletService
from wallet.infrastructure.balance_recoder import BalanceRecordImpl
from wallet.infrastructure.repositories import SqlAlchemyWalletRepository


def build_wallet_service(session: AsyncSession, *, held_reader: HeldAmountReader) -> WalletService:
    """같은 요청 세션으로 WalletService를 조립한다.

    held_reader: 예약 금액 조회. 경매가 제공하는 구현(AuctionHeldAmountReader)을 호출 측이 넘긴다.
      - 지갑은 listings 테이블이나 경매 저장소를 직접 읽지 않는다. 기본값·우회 경로는 두지 않는다.
      - 경매: WalletGatewayAdapter(build_wallet_service(session, held_reader=<경매의 reader>))
      - 지갑 API: main.py가 create_wallet_router에 reader 생성 함수를 주입한다.

    세션 종료와 commit/rollback은 호출자가 담당한다.
    잔액 변경 로그는 BalanceRecordImpl이 이 세션의 commit/rollback 이벤트에 붙어 자동으로 처리한다.
    관리자 확인은 users의 AdminRoleChecker를 그대로 쓴다 (없는·일반·탈퇴·정지 회원은 False → 충전 403).
    """
    return WalletService(
        roleCheck=build_admin_role_checker(session),
        logger=BalanceRecordImpl(session),
        wallet_repo=SqlAlchemyWalletRepository(session=session),
        held_reader=held_reader,
    )

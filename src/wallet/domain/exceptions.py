"""지갑 도메인 예외

shared.core.exceptions의 큰 분류를 상속한다.
HTTP 상태 코드는 여기서 정하지 않는다. presentation의 공통 핸들러가 부모 분류로 결정한다.
  BusinessRuleError → 400, NotFoundError → 404, ForbiddenError → 403,
  분류 없는 AppError → 500
"""
from shared.core.exceptions import AppError, BusinessRuleError, NotFoundError


class WalletNotFoundError(NotFoundError):
    code = "WALLET_NOT_FOUND"
    message = "지갑을 찾을 수 없습니다."


class TradeNotFoundError(NotFoundError):
    # WALL-05: 없는 거래, 그리고 당사자가 아닌 사용자의 조회 모두 이 예외 (존재 여부를 숨긴다)
    code = "TRADE_NOT_FOUND"
    message = "거래를 찾을 수 없습니다."


class InsufficientBalanceError(BusinessRuleError):
    # WALL-07: 입찰액(증액이면 차액)이 사용 가능 금액을 넘음. AUCT-01이 그대로 전달
    code = "INSUFFICIENT_BALANCE"
    message = "사용 가능한 골드가 부족합니다."


class BuyerBalanceShortError(AppError):
    # WALL-08: 정산 시 구매자 잔액 < 낙찰가. 예약 규칙이 지켜지면 생기지 않는 불일치다.
    # 일부러 분류(400/404)를 주지 않아 핸들러가 500으로 처리하고 예외 종류만 로그에 남긴다.
    code = "BUYER_BALANCE_SHORT"
    message = "정산 중 잔액 불일치가 발생했습니다."

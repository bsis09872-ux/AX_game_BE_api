"""지갑 업무 규칙 (DB 없이 계산만 하는 순수 함수)

service가 DB에서 읽은 값(잔액, 예약 합계, 매물의 현재 입찰 정보)을 넘기면
여기서 판정만 한다. 잠금·저장·로그는 하지 않는다.

예약 합계(held_amount)는 경매가 제공하는 HeldAmountReader로 읽는다:
  내가 최고 입찰자인 BIDDING 매물들의 입찰액 합계 (마감이 지나도 정산 전이면 포함)
"""
from dataclasses import dataclass

from wallet.domain.exceptions import BuyerBalanceShortError, InsufficientBalanceError

# 가입 시 지급하는 초기 골드 (WALL-06). 초안 값, 회의에서 확정한다.
INITIAL_BALANCE = 3_000


def available_balance(balance: int, held_amount: int) -> int:
    """사용 가능 금액 = 총잔액 - 예약 합계 (WALL-01)"""
    return balance - held_amount


def required_extra(
    *,
    bidder_id: int,
    amount: int,
    current_bidder_id: int | None,
    current_bid_amount: int | None,
) -> int:
    """이번 입찰로 새로 묶이는 금액 (WALL-07)

    경매 정책상 현재 최고 입찰자는 재입찰할 수 없다(AUCT-01이 막는다).
    그래서 입찰자는 항상 새 입찰자이고, 묶이는 금액은 입찰액 전액이다.
    최고가보다 높은지, 최소 인상폭을 넘는지, 재입찰인지는 경매 쪽(AUCT-01)이 먼저 검사한다.
    재입찰이 여기까지 오면 경매 검사 누락이므로 예외로 막는다.
    (정책이 바뀌어 증액을 허용하면 그때 '차액만 묶기' 계산을 추가한다)
    """
    if amount <= 0:
        raise ValueError("입찰액은 0보다 커야 합니다.")
    if (current_bidder_id is None) != (current_bid_amount is None):
        # ERD 일관성 조건: 입찰자와 금액은 둘 다 NULL이거나 둘 다 값이 있다
        raise ValueError("current_bidder_id와 current_bid_amount가 함께 있어야 합니다.")
    if current_bidder_id == bidder_id:
        raise ValueError("현재 최고 입찰자는 재입찰할 수 없습니다.")
    return amount


@dataclass(frozen=True)
class BidFundsCheck:
    required_extra: int
    available_before: int
    available_after: int


def check_bid_funds(*, balance: int, held_amount: int, extra: int) -> BidFundsCheck:
    """새로 묶일 금액이 사용 가능 금액 안인지 확인 (WALL-07)

    held_amount는 내가 최고 입찰자인 다른 매물들의 입찰액 합계다.
    """
    before = available_balance(balance, held_amount)
    if extra > before:
        raise InsufficientBalanceError()
    return BidFundsCheck(required_extra=extra, available_before=before, available_after=before - extra)


@dataclass(frozen=True)
class SettlementAmounts:
    buyer_debit: int    # 구매자 잔액에서 뺄 금액 = 낙찰가
    seller_credit: int  # 판매자 잔액에 더할 금액 = 낙찰가 (거래 수수료 없음)


def settlement_amounts(*, price: int, buyer_balance: int) -> SettlementAmounts:
    """낙찰 정산 금액 (WALL-08)

    수수료는 없다(팀 정책 확정). 구매자 -낙찰가, 판매자 +낙찰가.
    예약 규칙이 지켜졌다면 구매자 잔액은 항상 낙찰가 이상이다.
    아니면 데이터 불일치이므로 500으로 처리되는 예외를 던진다.
    """
    if price <= 0:
        raise ValueError("낙찰가는 0보다 커야 합니다.")
    if buyer_balance < price:
        raise BuyerBalanceShortError()
    return SettlementAmounts(buyer_debit=price, seller_credit=price)

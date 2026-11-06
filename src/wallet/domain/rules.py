"""지갑 업무 규칙 (DB 없이 계산만 하는 순수 함수)

service가 DB에서 읽은 값(잔액, 예약 합계, 매물의 현재 입찰 정보)을 넘기면
여기서 판정만 한다. 잠금·저장·로그는 하지 않는다.

예약 합계(held_amount)는 DB에서 계산한다:
  내가 current_bidder_id인 BIDDING 매물들의 current_bid_amount 합계
  (마감이 지나도 정산 전이면 포함)
"""
from dataclasses import dataclass

from wallet.domain.exceptions import BuyerBalanceShortError, InsufficientBalanceError

# 거래 수수료(%) — 미정이라 0. 정해지면 이 값만 바꾼다. 1골드 미만은 버린다.
FEE_PERCENT = 0

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

    - 첫 입찰이거나 다른 사람의 최고가를 갱신: 입찰액 전액
    - 내가 이미 최고 입찰자인데 증액: 이미 묶인 내 금액을 뺀 차액
    최고가보다 높은지, 최소 인상폭을 넘는지는 경매 쪽(AUCT-01)이 먼저 검사한다.
    """
    if amount <= 0:
        raise ValueError("입찰액은 0보다 커야 합니다.")
    if (current_bidder_id is None) != (current_bid_amount is None):
        # ERD 일관성 조건: 입찰자와 금액은 둘 다 NULL이거나 둘 다 값이 있다
        raise ValueError("current_bidder_id와 current_bid_amount가 함께 있어야 합니다.")
    if current_bidder_id == bidder_id:
        extra = amount - current_bid_amount
        if extra <= 0:
            raise ValueError("증액은 현재 내 입찰액보다 커야 합니다.")
        return extra
    return amount


@dataclass(frozen=True)
class BidFundsCheck:
    required_extra: int
    available_before: int
    available_after: int


def check_bid_funds(*, balance: int, held_amount: int, extra: int) -> BidFundsCheck:
    """새로 묶일 금액이 사용 가능 금액 안인지 확인 (WALL-07)

    held_amount는 이번 매물의 기존 내 입찰액을 이미 포함한 값이다.
    그래서 증액이면 extra(차액)만 비교하면 된다.
    """
    before = available_balance(balance, held_amount)
    if extra > before:
        raise InsufficientBalanceError()
    return BidFundsCheck(required_extra=extra, available_before=before, available_after=before - extra)


def fee_for(price: int) -> int:
    """거래 수수료. 1골드 미만 버림."""
    return price * FEE_PERCENT // 100


@dataclass(frozen=True)
class SettlementAmounts:
    buyer_debit: int   # 구매자 잔액에서 뺄 금액
    seller_credit: int  # 판매자 잔액에 더할 금액
    fee: int


def settlement_amounts(*, price: int, buyer_balance: int) -> SettlementAmounts:
    """낙찰 정산 금액 (WALL-08)

    예약 규칙이 지켜졌다면 구매자 잔액은 항상 낙찰가 이상이다.
    아니면 데이터 불일치이므로 500으로 처리되는 예외를 던진다.
    """
    if price <= 0:
        raise ValueError("낙찰가는 0보다 커야 합니다.")
    if buyer_balance < price:
        raise BuyerBalanceShortError()
    fee = fee_for(price)
    return SettlementAmounts(buyer_debit=price, seller_credit=price - fee, fee=fee)

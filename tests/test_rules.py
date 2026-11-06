"""wallet.domain.rules 단위 테스트

명세의 검증 항목을 그대로 옮겼다. DB가 필요 없어 바로 실행된다.
실행: 레포 최상위에서 `pytest tests/wallet` (src가 import 경로에 있어야 함)
"""
import pytest

from wallet.domain import rules
from wallet.domain.exceptions import BuyerBalanceShortError, InsufficientBalanceError


# ---------- WALL-01 사용 가능 금액 ----------

def test_available_is_balance_minus_held():
    # 명세 예시: 총잔액 100,000, 예약 70,000 → 사용 가능 30,000
    assert rules.available_balance(100_000, 70_000) == 30_000


def test_available_with_no_bids_equals_balance():
    assert rules.available_balance(3_000, 0) == 3_000


# ---------- WALL-07 새로 묶이는 금액 ----------

def test_first_bid_requires_full_amount():
    assert rules.required_extra(bidder_id=2, amount=50_000,
                                current_bidder_id=None, current_bid_amount=None) == 50_000


def test_outbidding_someone_else_requires_full_amount():
    assert rules.required_extra(bidder_id=2, amount=60_000,
                                current_bidder_id=7, current_bid_amount=50_000) == 60_000


def test_raising_own_bid_requires_only_difference():
    assert rules.required_extra(bidder_id=2, amount=60_000,
                                current_bidder_id=2, current_bid_amount=50_000) == 10_000


def test_raising_own_bid_must_increase():
    with pytest.raises(ValueError):
        rules.required_extra(bidder_id=2, amount=50_000,
                             current_bidder_id=2, current_bid_amount=50_000)


def test_bidder_and_amount_must_be_set_together():
    with pytest.raises(ValueError):
        rules.required_extra(bidder_id=2, amount=1_000,
                             current_bidder_id=7, current_bid_amount=None)


def test_non_positive_bid_rejected():
    with pytest.raises(ValueError):
        rules.required_extra(bidder_id=2, amount=0,
                             current_bidder_id=None, current_bid_amount=None)


# ---------- WALL-07 사용 가능 금액 확인 ----------

def test_bid_within_available_passes():
    # 명세 예시: 사용 가능 100,000에서 50,000 입찰 → 50,000 남음
    result = rules.check_bid_funds(balance=100_000, held_amount=0, extra=50_000)
    assert result == rules.BidFundsCheck(required_extra=50_000,
                                         available_before=100_000, available_after=50_000)


def test_bid_using_exact_available_passes():
    assert rules.check_bid_funds(balance=3_000, held_amount=2_000, extra=1_000).available_after == 0


def test_bid_over_available_is_insufficient():
    with pytest.raises(InsufficientBalanceError) as e:
        rules.check_bid_funds(balance=100_000, held_amount=70_000, extra=30_001)
    assert e.value.code == "INSUFFICIENT_BALANCE"


def test_raise_uses_difference_against_held_that_includes_own_bid():
    # 잔액 60,000, 이 매물에 내 입찰 50,000이 이미 예약됨 → 사용 가능 10,000
    # 60,000으로 증액: 차액 10,000이라 통과, 60,000 전액이면 실패해야 한다
    extra = rules.required_extra(bidder_id=2, amount=60_000,
                                 current_bidder_id=2, current_bid_amount=50_000)
    assert rules.check_bid_funds(balance=60_000, held_amount=50_000, extra=extra).available_after == 0
    with pytest.raises(InsufficientBalanceError):
        rules.check_bid_funds(balance=60_000, held_amount=50_000, extra=60_000)


# ---------- WALL-08 낙찰 정산 ----------

def test_settlement_project_example():
    # 개요 예시: B 잔액 3,000, 철검 1,000 → B 2,000, A +1,000
    s = rules.settlement_amounts(price=1_000, buyer_balance=3_000)
    assert (s.buyer_debit, s.seller_credit, s.fee) == (1_000, 1_000, 0)


def test_settlement_keeps_total_gold_when_no_fee():
    s = rules.settlement_amounts(price=15_000, buyer_balance=15_000)
    assert s.buyer_debit - s.seller_credit == s.fee == 0


def test_settlement_buyer_short_is_internal_error():
    with pytest.raises(BuyerBalanceShortError):
        rules.settlement_amounts(price=15_000, buyer_balance=14_999)


def test_fee_rounds_down(monkeypatch):
    # 수수료가 5%로 정해지면: 999골드 → 49 (49.95 버림), 판매자 950
    monkeypatch.setattr(rules, "FEE_PERCENT", 5)
    s = rules.settlement_amounts(price=999, buyer_balance=999)
    assert (s.fee, s.seller_credit) == (49, 950)

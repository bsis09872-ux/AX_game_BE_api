"""wallet.domain.wallet 단위 테스트 (Balance, Wallet)"""
from datetime import datetime, timezone

import pytest

from wallet.domain.exceptions import InsufficientBalanceError
from wallet.domain.wallet import Balance, Wallet
from wallet.infrastructure.balance_recoder import BalanceRecordImpl

NOW = datetime(2026, 11, 6, tzinfo=timezone.utc)


# ---------- Balance ----------

def test_balance_plus():
    b = Balance(1_000)
    b.plus(500)
    assert b.value == 1_500


def test_balance_minus():
    b = Balance(1_000)
    b.minus(1_000)
    assert b.value == 0


def test_balance_minus_more_than_value_fails_and_keeps_value():
    b = Balance(1_000)
    with pytest.raises(InsufficientBalanceError):
        b.minus(1_001)
    assert b.value == 1_000


def test_balance_default_is_zero():
    assert Balance().value == 0


# ---------- Wallet ----------

def test_wallet_add_balance_records_change():
    logger = BalanceRecordImpl()
    w = Wallet(1, Balance(3_000), NOW)

    w.add_balance(2_000, logger)

    assert w.balance.value == 5_000
    [c] = logger.pending
    assert (c.event_type, c.user_id, c.balance_before, c.amount, c.balance_after) == (
        "BALANCE_CREDIT", 1, 3_000, 2_000, 5_000)


def test_wallet_subtract_balance_records_change():
    logger = BalanceRecordImpl()
    w = Wallet(1, Balance(3_000), NOW)

    w.subtract_balance(1_000, logger)

    assert w.balance.value == 2_000
    [c] = logger.pending
    assert (c.event_type, c.balance_before, c.amount) == ("BALANCE_DEBIT", 3_000, -1_000)


def test_wallet_event_type_can_be_given():
    logger = BalanceRecordImpl()
    w = Wallet(1, Balance(3_000), NOW)

    w.subtract_balance(1_000, logger, "PURCHASE_DEBIT")
    w.add_balance(1_000, logger, "SALE_CREDIT")

    assert [c.event_type for c in logger.pending] == ["PURCHASE_DEBIT", "SALE_CREDIT"]


def test_wallet_subtract_too_much_fails_without_log():
    logger = BalanceRecordImpl()
    w = Wallet(1, Balance(3_000), NOW)

    with pytest.raises(InsufficientBalanceError):
        w.subtract_balance(3_001, logger)
    assert w.balance.value == 3_000
    assert logger.pending == []

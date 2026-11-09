"""BalanceRecordImpl 세션 이벤트 테스트: commit이면 로그가 남고, rollback이면 버려진다.

PostgreSQL 없이 메모리 SQLite 동기 세션으로 세션 이벤트(after_commit/after_rollback)만 확인한다.
(AsyncSession도 내부의 sync_session에 같은 이벤트가 붙는다)
"""
import logging

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from wallet.infrastructure.balance_recoder import BalanceRecordImpl

LOGGER = "wallet.infrastructure.balance_log"


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    with Session(engine) as s:
        yield s
    engine.dispose()


def balance_logs(caplog):
    return [r.getMessage() for r in caplog.records if r.name == LOGGER]


def test_commit_writes_pending_changes(session, caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    recorder = BalanceRecordImpl(session)
    recorder.logging(1, 0, 3_000, "INITIAL_GRANT")

    session.execute(text("select 1"))  # 트랜잭션 시작
    assert balance_logs(caplog) == []  # commit 전에는 남기지 않는다
    session.commit()

    [message] = balance_logs(caplog)
    assert "event_type=INITIAL_GRANT user_id=1" in message
    assert "balance_before=0 amount=3000 balance_after=3000" in message
    assert recorder.pending == []


def test_rollback_discards_pending_changes(session, caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    recorder = BalanceRecordImpl(session)
    recorder.logging(1, 3_000, 1_800, "PURCHASE_DEBIT")

    session.execute(text("select 1"))
    session.rollback()

    assert balance_logs(caplog) == []
    assert recorder.pending == []


def test_each_commit_writes_only_its_own_changes(session, caplog):
    # 스케줄러처럼 한 세션에서 매물마다 commit하는 경우: 이미 남긴 변경을 다시 남기지 않는다
    caplog.set_level(logging.INFO, logger=LOGGER)
    recorder = BalanceRecordImpl(session)

    recorder.logging(1, 3_000, 1_800, "PURCHASE_DEBIT")
    session.execute(text("select 1"))
    session.commit()
    recorder.logging(2, 500, 1_700, "SALE_CREDIT")
    session.execute(text("select 1"))
    session.commit()

    messages = balance_logs(caplog)
    assert len(messages) == 2
    assert "user_id=1" in messages[0] and "user_id=2" in messages[1]


def test_without_session_needs_manual_flush(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER)
    recorder = BalanceRecordImpl()
    recorder.logging(1, 0, 3_000, "INITIAL_GRANT")

    assert balance_logs(caplog) == []
    recorder.flush()
    assert len(balance_logs(caplog)) == 1

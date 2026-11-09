"""BalanceRecord 구현: 잔액 변경을 모아 두었다가 commit 성공 뒤에 로그로 남긴다.

infrastructure/balance_log.py 규칙대로 commit 전에는 로그를 쓰지 않는다.
도메인이 logging()을 부르면 버퍼에만 쌓는다.

세션을 넘기면(wiring이 넘긴다) 세션 이벤트에 붙어서 스스로 처리한다.
  - commit 성공(after_commit)   → flush(): 쌓인 변경을 로그로 남긴다
  - rollback(after_rollback)    → discard(): 쌓인 변경을 버린다
그래서 호출자(지갑 라우터, 경매 TransactionManager 등)는 commit/rollback만 하면 되고
지갑 로그를 따로 신경 쓰지 않는다. 세션 없이 만들면(테스트) flush/discard를 직접 부른다.
"""
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from wallet.domain.balance_change import BalanceChange
from wallet.domain.service import BalanceEventType, BalanceRecord
from wallet.infrastructure.balance_log import log_balance_changes


class BalanceRecordImpl(BalanceRecord):
    def __init__(self, session: AsyncSession | Session | None = None) -> None:
        self._pending: list[BalanceChange] = []
        if session is not None:
            self._attach(session)

    def _attach(self, session: AsyncSession | Session) -> None:
        # 세션 이벤트는 동기 Session에 등록한다. AsyncSession은 내부의 sync_session을 쓴다.
        sync_session = getattr(session, "sync_session", session)
        event.listen(sync_session, "after_commit", self._on_commit)
        event.listen(sync_session, "after_rollback", self._on_rollback)

    def _on_commit(self, _session: Session) -> None:
        self.flush()

    def _on_rollback(self, _session: Session) -> None:
        self.discard()

    def logging(
        self, user_id: int, prev_balance: int, current_balance: int, event_type: BalanceEventType
    ):
        amount = current_balance - prev_balance
        self._pending.append(
            BalanceChange(
                event_type=event_type,
                user_id=user_id,
                balance_before=prev_balance,
                amount=amount,
            )
        )

    @property
    def pending(self) -> list[BalanceChange]:
        return list(self._pending)

    def flush(self, request_id: str | None = None) -> None:
        """commit 성공 뒤: 쌓인 변경을 로그로 남기고 비운다 (세션에 붙어 있으면 자동 호출)"""
        if not self._pending:
            return
        log_balance_changes(self._pending, request_id)
        self._pending.clear()

    def discard(self) -> None:
        """rollback 시: 확정되지 않은 변경을 버린다 (세션에 붙어 있으면 자동 호출)"""
        self._pending.clear()

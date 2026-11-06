"""BalanceRecord 구현: 잔액 변경을 모아 두었다가 commit 성공 뒤에 로그로 남긴다.

balance_log.py 규칙대로 commit 전에는 로그를 쓰지 않는다.
도메인이 logging()을 부르면 버퍼에만 쌓고, 호출자가 commit 성공 뒤 flush()를 부른다.
commit이 실패하면 flush 대신 discard()로 버린다.
"""
from wallet.application.balance_log import BalanceChange, log_balance_changes
from wallet.domain.service import BalanceRecord


class BalanceRecordImpl(BalanceRecord):
    def __init__(self) -> None:
        self._pending: list[BalanceChange] = []

    def logging(self, user_id: int, prev_balance: int, current_balance: int):
        amount = current_balance - prev_balance
        self._pending.append(
            BalanceChange(
                event_type="BALANCE_CREDIT" if amount >= 0 else "BALANCE_DEBIT",
                user_id=user_id,
                balance_before=prev_balance,
                amount=amount,
            )
        )

    @property
    def pending(self) -> list[BalanceChange]:
        return list(self._pending)

    def flush(self, request_id: str | None = None) -> None:
        """commit 성공 뒤에 호출"""
        log_balance_changes(self._pending, request_id)
        self._pending.clear()

    def discard(self) -> None:
        """rollback 시 호출"""
        self._pending.clear()

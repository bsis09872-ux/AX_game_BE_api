"""잔액 변경 로그 (Ver_4.0: wallet_entries 대신 서버 로그)

팀 규칙대로 logging.getLogger(__name__)만 쓰고 handler는 붙이지 않는다.
출력 형식·대상은 shared.core.logging_config가 정한다.

메시지는 공통 핸들러와 같은 "이벤트명 key=value ..." 형식이다.
값에 공백이 없으므로 Grafana에서 LogQL `| logfmt`로 필드를 꺼낼 수 있다.

반드시 DB commit이 성공한 뒤에 호출한다. commit 전에 남기면
롤백된 변경이 확정된 것처럼 기록된다. 이 로그는 정산 성공 판정이나
중복 차감 방지의 기준이 아니다(그 기준은 DB의 trades UNIQUE와 매물 상태).
"""
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

# 종류 목록은 도메인(BalanceRecord 계약)이 정한다
from wallet.domain.service import BalanceEventType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BalanceChange:
    """서비스가 트랜잭션 안에서 만들고, 호출자가 commit 뒤에 기록한다."""
    event_type: BalanceEventType
    user_id: int
    balance_before: int
    amount: int  # 증가는 양수, 감소는 음수
    listing_id: int | None = None
    trade_id: int | None = None

    @property
    def balance_after(self) -> int:
        return self.balance_before + self.amount


def _v(value: object) -> str:
    return "null" if value is None else str(value)


def log_balance_changes(changes: list[BalanceChange], request_id: str | None = None) -> None:
    occurred_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for c in changes:
        logger.info(
            "balance_changed event_id=%s request_id=%s event_type=%s user_id=%s "
            "listing_id=%s trade_id=%s balance_before=%s amount=%s balance_after=%s "
            "occurred_at=%s outcome=committed",
            uuid.uuid4(), _v(request_id), c.event_type, c.user_id,
            _v(c.listing_id), _v(c.trade_id), c.balance_before, c.amount, c.balance_after,
            occurred_at,
        )

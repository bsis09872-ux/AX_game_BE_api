"""잔액 변경 로그 (Ver_4.0: wallet_entries 대신 서버 로그)

팀 규칙대로 logging.getLogger(__name__)만 쓰고 handler는 붙이지 않는다.
출력 형식·대상은 shared.core.logging_config가 정한다.

메시지는 공통 핸들러와 같은 "이벤트명 key=value ..." 형식이다.
값에 공백이 없으므로 Grafana에서 LogQL `| logfmt`로 필드를 꺼낼 수 있다.

반드시 DB commit이 성공한 뒤에 호출한다. commit 전에 남기면
롤백된 변경이 확정된 것처럼 기록된다. 이 로그는 정산 성공 판정이나
중복 차감 방지의 기준이 아니다(그 기준은 DB의 trades UNIQUE와 매물 상태).

로그 출력은 바깥 세계(로깅 시스템)와 맞닿는 일이라 infrastructure에 둔다.
기록할 내용(BalanceChange)은 도메인이 정한다.
"""
import logging
import uuid
from datetime import datetime, timezone

from wallet.domain.balance_change import BalanceChange

logger = logging.getLogger(__name__)


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

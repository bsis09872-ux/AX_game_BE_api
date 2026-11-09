from collections import OrderedDict
from datetime import datetime, timezone
from uuid import UUID


class RevokedSessionCache:
    """확정된 폐기만 기억한다. 캐시 누락은 항상 DB 검증으로 이어진다."""

    def __init__(self, max_entries: int = 4096):
        self._entries: OrderedDict[UUID, datetime] = OrderedDict()
        self._max_entries = max_entries

    def contains(self, session_id: UUID) -> bool:
        expires_at = self._entries.get(session_id)
        if expires_at is None:
            return False
        if expires_at <= datetime.now(timezone.utc):
            del self._entries[session_id]
            return False
        return True

    def add(self, session_id: UUID, expires_at: datetime) -> None:
        now = datetime.now(timezone.utc)
        for key, deadline in list(self._entries.items()):
            if deadline <= now:
                del self._entries[key]
        if expires_at <= now:
            return
        self._entries[session_id] = expires_at
        self._entries.move_to_end(session_id)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

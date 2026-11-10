"""메시지 횟수 제한. 최근 window초 안에 받은 메시지 수를 센다."""

from collections import deque


class MessageBudget:
    def __init__(self, per_second: int, window: float = 1.0):
        self.per_second = per_second
        self.window = window
        self._times: deque[float] = deque()

    def allow(self, now: float) -> bool:
        while self._times and now - self._times[0] >= self.window:
            self._times.popleft()
        if len(self._times) >= self.per_second:
            return False
        self._times.append(now)
        return True

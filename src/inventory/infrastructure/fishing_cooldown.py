"""낚시 쿨다운(메모리): 같은 사용자는 정해진 초(기본 10초)에 한 번만 낚을 수 있다

- try_start는 쿨다운 중이 아니면 지금 시각을 기록하고 0을 돌려주고, 쿨다운 중이면 남은 초(올림)를 돌려준다
- 거절된 시도는 기록을 바꾸지 않는다 (연타해도 쿨다운이 늘어나지 않는다)
- 메모리에 있어서 서버를 다시 켜면 초기화되고, 서버가 여러 대면 사용자별 쿨다운이 어긋난다
- 요청마다 새로 만들면 기록이 사라져 항상 통과하므로 하나를 계속 쓴다
- 현재 시각은 인자로 받는다 (테스트에서 시간을 흘려보낼 수 있게 한다)
"""

import math
from datetime import datetime

class InMemoryFishingCooldown:
    def __init__(self, seconds: int = 10) -> None:
        self._seconds = seconds
        # 마지막으로 낚시를 시작한 시각 / 스킬을 쓰는 순간부터 발동되는 쿨타임
        self._last_started: dict[int, datetime] = {}

    async def try_start(self, user_id: int, now: datetime) -> int:
        last = self._last_started.get(user_id)
        if last is not None:
            elapsed = (now-last).total_seconds()
            if elapsed < self._seconds:
                # 낚시 시도 거절
                return min(self._seconds, math.ceil(self._seconds-elapsed))

        self._last_started[user_id] = now
        return 0
        
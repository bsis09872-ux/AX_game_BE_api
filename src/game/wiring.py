"""낚시터의 부품 조립: 계약에 맞는 어댑터를 만들어 돌려준다

- 다른 도메인의 wiring을 이용해 어댑터를 조립한다 (다른 도메인의 infrastructure를 직접 import하지 않는다)
- 멀티플레이 허브는 하나만 만들어 계속 쓴다 (요청마다 만들면 방이 사라진다)
- WebSocket 로그인 확인은 요청 세션(get_db) 대신 짧은 세션을 따로 연다
- 설정은 환경변수로 바꿀 수 있다. 없으면 아래 기본값을 쓴다
- 업무 규칙을 두지 않는다
"""

import os
from functools import lru_cache

from database import AsyncSessionLocal
from game.application.contracts import PlayerDirectory
from game.application.hub import WorldHub
from game.infrastructure.adapters.player_directory import PlayerDirectoryAdapter


def _int_setting(name: str, default: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name}은 1 이상이어야 합니다.")
    return value


# 위치를 나눠 주는 횟수(초당), 맵 하나의 최대 인원, 메시지 한 통의 최대 크기(바이트), 연결마다 보낼 대기열 크기
TICK_HZ = _int_setting("GAME_TICK_HZ", 10)
ROOM_CAPACITY = _int_setting("GAME_ROOM_CAPACITY", 20)
MAX_MESSAGE_BYTES = _int_setting("GAME_MAX_MESSAGE_BYTES", 1024)
SEND_QUEUE_SIZE = _int_setting("GAME_SEND_QUEUE_SIZE", 64)


@lru_cache
def get_world_hub() -> WorldHub:
    return WorldHub(tick_hz=TICK_HZ, room_capacity=ROOM_CAPACITY)


@lru_cache
def get_player_directory() -> PlayerDirectory:
    # WebSocket은 요청 세션(get_db)을 쓰지 않으므로 세션 공장을 넘긴다
    return PlayerDirectoryAdapter(session_factory=AsyncSessionLocal)

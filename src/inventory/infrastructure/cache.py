"""아이템 카탈로그 조회용 메모리 캐시

범위를 이렇게 잡은 이유
- 선택 과제이다
- 카탈로그 목록·상세만 캐시한다: 모든 사용자에게 같은 값이고, 자주 읽히며, 가끔만 바뀐다
- 예약·이전·지급 판정, 내 인벤토리, 낚시에는 쓰지 않는다: 판정은 항상 DB 최신값이어야 한다
- 값은 수정할 수 없는 DTO만 넣는다: 도메인 객체를 넣으면 수정이 캐시 속 객체를 바로 바꾼다
- 카탈로그가 바뀌면(생성·수정·삭제 commit 뒤) 캐시 전체를 지운다: 부분 삭제는 목록 캐시를 놓치기 쉽다
- 만료 시간(TTL)은 설정으로 바꾸고, 시간은 밖에서 주입한다: 테스트에서 시간을 흘려보내기 위해

한계
- 프로세스 메모리라 서버를 다시 켜면 사라지고, 서버를 여러 개 띄우면 서로 다른 값을 볼 수 있다 (시연은 서버 1개)
- None은 "없음"을 뜻하므로 값으로 넣지 않는다
"""


import time
from collections.abc import Callable


# 키마다 만료 시각을 두는 메모리 캐시 (TTL초가 지나면 없는 값으로 간주)
class TtlCache:

    def __init__(
        self,
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic
    ) -> None:
        
        # 0 이하면 넣자마자 만료되어 캐시 의미가 없으므로 만들 때 막는다
        if ttl_seconds <= 0:
            raise ValueError('ttl_seconds는 0보다 커야 합니다.')
        self._ttl_seconds = ttl_seconds

        # 시간을 밖에서 받는다 (테스트용)
        self._clock = clock

        # {키: (값, 만료 시각)}
        self._entries: dict[str, tuple[object, float]] = {}


    # 만료 전이면 값을, 값이 없거나 만료되었으면 None
    def get(self, key: str) -> object | None:

        entry = self._entries.get(key)

        if entry is None:
            return None
        value, expires_at = entry

        # 만료 시각이 되는 순간부터 만료
        if self._clock() >= expires_at:

            # 만료된 항목은 지워서 메모리에 쌓이지 않게 한다
            del self._entries[key]
            return None
        
        return value


    # 값을 넣었는데 같은 키가 있으면 값과 만료 시각을 다시 설정
    def set(self, key: str, value: object) -> None:
        self._entries[key] = (value, self._clock() + self._ttl_seconds)


    # 모든 키를 한 번에 삭제 (카탈로그가 바뀔 때 사용)
    def clear(self) -> None:
        self._entries.clear()
"""인벤토리가 다른 도메인에 요청하는 기능의 계약 (내가 필요한 것)

- 계약은 필요한 기능의 모양(Protocol)만 적는다. 구현은 어댑터가 하고 wiring이 연결한다
- UserLookup: 주어진 사용자 번호 중 실제로 있고 탈퇴하지 않은(활성) 번호만 돌려준다
- 다른 도메인의 모델이나 infrastructure를 import하지 않는다
"""

from collections.abc import Iterable
from typing import Protocol

# 쓰는 쪽은 이 모양만 알고 누가 어떻게 구현했는지는 모른다
class UserLookup(Protocol):
    # user_ids 중 활성인 번호만 set으로 돌려준다 (없거나 탈퇴한 번호는 제외)
    async def find_active_user_ids(self, user_ids: Iterable[int]) -> set[int]:
        ...

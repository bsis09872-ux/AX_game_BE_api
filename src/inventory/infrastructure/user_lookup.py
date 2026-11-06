"""회원 조회 어댑터: UserLookup 계약을 users 도메인의 서비스에 연결한다

- users 서비스의 get_user_summary로만 회원을 묻는다 (회원 모델이나 테이블을 직접 읽지 않는다)
- 없는 회원(UserNotFoundError)은 건너뛰고, 탈퇴한 회원(is_active가 거짓)은 결과에서 뺀다
- 그 밖의 오류는 그대로 올려 보낸다
"""

from collections.abc import Iterable

from inventory.application.contracts import UserLookup

from users.application.service import UserService
from users.domain.exceptions import UserNotFoundError

class UserLookupAdapter(UserLookup):
    
    def __init__(self, user_service: UserService) -> None:
        self._user_service = user_service

    async def find_active_user_ids(self, user_ids: Iterable[int]) -> set[int]:
        active: set[int] = set()
        
        for user_id in set(user_ids):
            try:
                summary = await self._user_service.get_user_summary(user_id)
            except UserNotFoundError:
                continue
            if summary.is_active:
                active.add(user_id)
        return active
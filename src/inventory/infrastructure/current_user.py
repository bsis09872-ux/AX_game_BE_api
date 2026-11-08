"""현재 사용자 어댑터: auth의 토큰 확인 결과를 인벤토리의 CurrentUser로 바꾼다

- auth의 서비스(authenticate)를 통해서만 토큰을 확인한다 (auth의 infrastructure를 직접 import하지 않는다)
- 토큰이 틀렸거나 만료돼서 인증 오류가 나면 None을 돌려준다 (401로 바꾸는 일은 presentation의 의존성이 한다)
- 인증 오류가 아닌 오류는 삼키지 않고 그대로 올린다
- 역할(role)은 auth가 아직 제공하지 않아서 임시 관리자 번호만 'ADMIN', 나머지는 'USER'로 한다 (users의 role을 읽을 수 있게 되면 그 값으로 바꾼다. 관리자는 'USER'를 'ADMIN'으로 승격하는 방식으로 만든다)
- 업무 규칙을 두지 않는다
"""

from auth.application.service import AuthService
from auth.domain.exceptions import AuthenticationError
from inventory.application.contracts import CurrentUser

# [TO DO][임시] 관리자 번호를 코드에 직접 둔 임시값이다. users가 UserSummary.role을 제공하면 이 상수를 지우고 그 값을 쓴다
_TEMP_ADMIN_IDS = frozenset({1})

class CurrentUserAdapter:

    def __init__(self, auth_service: AuthService) -> None:
        self._auth_service = auth_service

    async def authenticate(self, access_token: str) -> CurrentUser | None:
        try:
            claims = await self._auth_service.authenticate(access_token)
        except AuthenticationError:
            # 틀렸거나 만료된 토큰
            return None

        # [TO DO][임시] role 판정도 UserSummary.role로 교체한다
        role = 'ADMIN' if claims.user_id in _TEMP_ADMIN_IDS else 'USER'
        return CurrentUser(id=claims.user_id, role=role)
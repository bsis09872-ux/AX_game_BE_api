"""현재 사용자 어댑터: auth의 토큰 확인 결과를 인벤토리의 CurrentUser로 바꾼다

- auth의 서비스(authenticate)를 통해서만 토큰을 확인한다 (auth의 infrastructure를 직접 import하지 않는다)
- 토큰이 틀렸거나 만료돼서 인증 오류가 나면 None을 돌려준다 (401로 바꾸는 일은 presentation의 의존성이 한다)
- 인증 오류가 아닌 오류는 삼키지 않고 그대로 올린다
- 역할은 인증된 회원 번호로 조회한 현재 회원 정보에서 가져온다
- 업무 규칙을 두지 않는다
"""

from auth.application.service import AuthService
from auth.domain.exceptions import AuthenticationError
from inventory.application.contracts import CurrentUser
from users.application.service import UserService
from users.domain.exceptions import UserNotFoundError

class CurrentUserAdapter:

    def __init__(self, auth_service: AuthService, user_service: UserService) -> None:
        self._auth_service = auth_service
        self._user_service = user_service

    async def authenticate(self, access_token: str) -> CurrentUser | None:
        try:
            claims = await self._auth_service.authenticate(access_token)
            user = await self._user_service.get_user_summary(claims.user_id)
        except (AuthenticationError, UserNotFoundError):
            # 틀렸거나 만료된 토큰
            return None

        if not user.is_active:
            return None
        return CurrentUser(id=user.id, role=user.role)

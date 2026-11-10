"""Adapter: 낚시터의 PlayerDirectory 계약을 auth·users 서비스에 연결한다

- 토큰 확인은 auth의 authenticate(서명·만료·로그아웃 여부)를 그대로 쓴다. 토큰을 직접 해석하지 않는다
- 닉네임과 활성 여부는 users가 공개한 get_user_summary로 읽는다
- WebSocket은 오래 열려 있으므로 DB 세션을 연결 내내 잡지 않고, 확인할 때만 잠깐 연다
- 토큰과 쿠키 값은 로그에 남기지 않는다
"""

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from auth.domain.exceptions import AuthenticationError
from auth.wiring import build_auth_service
from game.application.contracts import PlayerDirectory
from game.application.dto import PlayerIdentity
from users.domain.exceptions import UserNotFoundError
from users.wiring import build_user_service


class PlayerDirectoryAdapter(PlayerDirectory):
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def authenticate(self, access_token: str) -> PlayerIdentity | None:
        if not access_token:
            return None
        async with self._session_factory() as session:
            try:
                claims = await build_auth_service(session).authenticate(access_token)
                user = await build_user_service(session=session).get_user_summary(claims.user_id)
            except (AuthenticationError, UserNotFoundError):
                # 틀렸거나 만료된 토큰, 없는 회원
                return None
        if not user.is_active:
            return None
        return PlayerIdentity(user_id=user.id, nickname=user.display_name)

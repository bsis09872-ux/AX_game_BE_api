# users의 조회 결과를 인증에 필요한 데이터로 바꾸는 도메인 연결 어댑터다.
from auth.application.contracts import UserReader
from auth.application.dto import AuthUser
from users.application.service import UserService
from users.domain.exceptions import UserNotFoundError
from users.domain.user import User


class UserReaderAdapter(UserReader):
    def __init__(self, user_service: UserService):
        self._user_service = user_service

    @staticmethod
    def _to_auth_user(user: User) -> AuthUser:
        if user.id is None:
            raise RuntimeError("회원 조회 결과에 ID가 없습니다.")
        return AuthUser(
            id=user.id, is_active=user.can_login(), password_hash=user.password_hash
        )

    async def find_by_login_id(self, login_id: str) -> AuthUser | None:
        # 로그인과 관리자 정지가 같은 회원 행을 잠가 세션 생성/폐기 순서를 맞춘다.
        user = await self._user_service.find_by_login_id_for_update(login_id)
        return self._to_auth_user(user) if user is not None else None

    async def find_by_id(self, user_id: int) -> AuthUser | None:
        try:
            user = await self._user_service.get_user(user_id)
        except UserNotFoundError:
            return None
        return self._to_auth_user(user)

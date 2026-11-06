# auth의 회원 생성 계약을 users 서비스에 연결하고 결과를 CreatedUser로 변환한다.
from auth.application.contracts import UserCreator, CreatedUser

from users.application.service import UserService

class UserCreatorAdapter(UserCreator):
    def __init__(self, user_service: UserService):
        self._user_service = user_service

    # 회원 생성 예외는 그대로 전파하며, 전체 가입의 commit은 호출자가 담당한다.
    async def create_user(
        self, login_id: str, display_name: str, password_hash: str
    ) -> CreatedUser:
        user = await self._user_service.create_user(
            login_id=login_id, display_name=display_name, password_hash=password_hash
        )

        # 저장 후 필수 값이 누락되면 불완전한 가입 결과를 반환하지 않는다.
        if user.id is None or user.created_at is None:
            raise RuntimeError("회원 생성 결과에 ID 또는 가입 시각이 없습니다.")

        # 인증 계층에는 비밀번호 해시를 제외한 생성 결과만 전달한다.
        return CreatedUser(
            id=user.id, login_id=user.login_id, created_at=user.created_at
        )

# AuthService에 비밀번호 해싱 구현과 회원 생성 어댑터를 연결한다.
from sqlalchemy.ext.asyncio import AsyncSession

from auth.application.service import AuthService
from auth.infrastructure.password_hasher import PasslibPasswordHasher
from auth.infrastructure.user_creator import UserCreatorAdapter

from users.wiring import build_user_service

def build_auth_service(session: AsyncSession) -> AuthService:
    # 요청 세션을 users 저장소까지 공유하며 세션 수명은 호출자가 관리한다.
    user_service = build_user_service(session=session)

    user_creator = UserCreatorAdapter(user_service=user_service)

    password_hasher = PasslibPasswordHasher()

    return AuthService(password_hasher=password_hasher, user_creator=user_creator)

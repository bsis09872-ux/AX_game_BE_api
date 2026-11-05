# 회원가입에 필요한 해싱과 회원 생성을 조율한다. 지갑 생성과 트랜잭션 확정은 연결 예정이다.
from auth.application.contracts import UserCreator, PasswordHasher, CreatedUser

class AuthService:
    def __init__(self, password_hasher: PasswordHasher, user_creator: UserCreator):
        self.password_hasher = password_hasher
        self.user_creator = user_creator

    # 중복 회원 등 의존성의 예외는 호출자에게 전파한다.
    async def register_user(self, login_id: str, display_name: str, password: str) -> CreatedUser:
        password_hash = await self.password_hasher.hash(password)

        user = await self.user_creator.create_user(login_id=login_id, display_name=display_name, password_hash=password_hash)

        # TODO: user.id로 초기 지갑 생성 기능을 호출한다. 실제 함수명은 wallet 구현과 맞춘다.
        # TODO: 회원과 지갑이 공유하는 트랜잭션을 commit한 뒤 가입 결과를 반환한다.
        # 현재 반환값은 저장 확정 전 결과다. 위 두 작업 연결 후 HTTP 가입 흐름에 사용한다.
        return user

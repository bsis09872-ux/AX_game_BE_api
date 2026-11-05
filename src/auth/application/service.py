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

        # 회원 생성은 flush까지 수행한다. 지갑 생성과 commit은 아직 연결하지 않았다.
        return user

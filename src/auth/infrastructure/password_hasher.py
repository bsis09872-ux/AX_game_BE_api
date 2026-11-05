# Passlib로 비밀번호를 해싱하고 PasswordHasher의 비동기 계약을 구현한다.
from asyncio import to_thread

from passlib.context import CryptContext

from auth.application.contracts import PasswordHasher


class PasslibPasswordHasher(PasswordHasher):
    def __init__(self):
        # bcrypt의 입력 길이 제한으로 비밀번호가 잘리지 않도록 bcrypt_sha256을 사용한다.
        self._context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")

    async def hash(self, password: str) -> str:
        # 동기 해싱을 별도 스레드에서 실행하며 실패 예외는 호출자에게 전파한다.
        return await to_thread(self._context.hash, password)

# auth에서 사용하는 해싱과 회원 생성의 계약 및 회원 생성 결과를 정의한다.
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

# 저장 후 발급된 ID와 가입 시각을 전달하며 비밀번호 정보는 제외한다.
@dataclass(frozen=True)
class CreatedUser:
    id: int
    login_id: str
    created_at: datetime

# 해싱 구현은 비동기 호출로 해시 문자열을 반환한다.
class PasswordHasher(Protocol):
    async def hash(self, password: str) -> str:
        ...

    # 비밀번호 일치 여부를 반환하며 해시 형식 오류와 검증 실패는 예외로 전달한다.
    async def verify(self, password: str, password_hash: str) -> bool:
        ...

# 회원 생성은 flush까지 수행하며 가입 전체의 commit은 호출자가 결정한다.
# 중복 로그인 ID는 LoginIdAlreadyExistsError로 전달한다.
class UserCreator(Protocol):
    async def create_user(self, login_id: str, display_name: str, password_hash: str) ->CreatedUser:
        ...

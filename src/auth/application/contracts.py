# 인증 서비스가 사용하는 외부 기능의 계약과 전달 데이터를 정의한다.
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class CreatedUser:
    id: int
    login_id: str
    created_at: datetime


@dataclass(frozen=True)
class AuthUser:
    id: int
    is_active: bool
    password_hash: str = field(repr=False)


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    jti: UUID
    expires_at: datetime
    session_id: UUID | None = None


@dataclass(frozen=True)
class IssuedToken:
    access_token: str = field(repr=False)
    expires_in: int


@dataclass(frozen=True)
class TokenPair:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_in: int
    refresh_expires_in: int


@dataclass(frozen=True)
class LoginSession:
    id: UUID
    user_id: int
    expires_at: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class RefreshState:
    session: LoginSession
    used_at: datetime | None


class RefreshTokenCodec(Protocol):
    def generate(self) -> str: ...

    def digest(self, token: str) -> str: ...


class SessionRepository(Protocol):
    async def create(self, session: LoginSession, token_hash: str) -> None: ...

    async def find(self, session_id: UUID) -> LoginSession | None: ...

    async def find_refresh_for_update(self, token_hash: str) -> RefreshState | None: ...

    async def rotate(
        self, session_id: UUID, old_hash: str, new_hash: str, used_at: datetime
    ) -> None: ...

    async def revoke(self, session_id: UUID, now: datetime) -> None: ...


class PasswordHasher(Protocol):
    async def hash(self, password: str) -> str: ...

    # 비밀번호 불일치는 False, 저장된 해시의 형식 오류는 예외로 전달한다.
    async def verify(self, password: str, password_hash: str) -> bool: ...


# 회원 생성은 flush까지 수행하며 가입 전체의 commit은 인증 서비스가 결정한다.
class UserCreator(Protocol):
    async def create_user(
        self, login_id: str, display_name: str, password_hash: str
    ) -> CreatedUser: ...


# 탈퇴 상태를 포함해 조회하며, 없는 회원은 None으로 전달한다.
class UserReader(Protocol):
    async def find_by_login_id(self, login_id: str) -> AuthUser | None: ...

    async def find_by_id(self, user_id: int) -> AuthUser | None: ...


class TokenCodec(Protocol):
    def issue(self, user_id: int, session_id: UUID | None = None) -> IssuedToken: ...

    def decode(self, token: str) -> TokenClaims: ...


class RevokedTokenRepository(Protocol):
    async def contains(self, jti: UUID) -> bool: ...

    # 동일 토큰의 반복 폐기는 성공으로 취급한다. commit은 포함하지 않는다.
    async def revoke(self, claims: TokenClaims) -> None: ...


class Transaction(Protocol):
    async def commit(self) -> None: ...

# 인증 계층 사이에서 전달하는 회원, 토큰과 로그인 세션 데이터를 정의한다.
from dataclasses import dataclass, field
from datetime import datetime
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
    session_id: UUID
    # JWT의 만료와 별개인 DB 로그인 세션의 최종 만료 시각이다.
    session_expires_at: datetime | None = None


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

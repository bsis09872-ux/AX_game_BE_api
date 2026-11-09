# 회원가입 저장, 로그인 토큰 발급, 인증 확인과 세션 폐기를 조율한다.
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from auth.application.contracts import (
    PasswordHasher,
    TokenCodec,
    Transaction,
    UserCreator,
    UserReader,
    RefreshTokenCodec,
    SessionRepository,
    RevokedSessions,
)
from auth.application.dto import (
    CreatedUser,
    TokenClaims,
    LoginSession,
    TokenPair,
)
from auth.domain.exceptions import InvalidCredentialsError, InvalidTokenError


class AuthService:
    def __init__(
        self,
        password_hasher: PasswordHasher,
        user_creator: UserCreator,
        user_reader: UserReader,
        token_codec: TokenCodec,
        transaction: Transaction,
        sessions: SessionRepository,
        refresh_codec: RefreshTokenCodec,
        refresh_ttl_seconds: int = 604800,
        revoked_sessions: RevokedSessions | None = None,
    ):
        self.password_hasher = password_hasher
        self.user_creator = user_creator
        self.user_reader = user_reader
        self.token_codec = token_codec
        self.transaction = transaction
        if not 30 <= refresh_ttl_seconds <= 2592000:
            raise ValueError("REFRESH_TTL_SECONDS는 30~2592000 사이여야 합니다.")
        self.sessions = sessions
        self.refresh_codec = refresh_codec
        self.refresh_ttl_seconds = refresh_ttl_seconds
        self.revoked_sessions = revoked_sessions

    def _cache_revoked(self, session: LoginSession) -> None:
        if self.revoked_sessions is not None:
            self.revoked_sessions.add(session.id, session.expires_at)

    async def register_user(
        self, login_id: str, display_name: str, password: str
    ) -> CreatedUser:
        password_hash = await self.password_hasher.hash(password)
        user = await self.user_creator.create_user(
            login_id=login_id, display_name=display_name, password_hash=password_hash
        )
        # 응답 전 저장을 확정한다. 실패 시 요청 세션의 get_db가 rollback한다.
        await self.transaction.commit()
        return user

    async def login(self, login_id: str, password: str) -> TokenPair:
        if not 4 <= len(login_id) <= 50 or not 1 <= len(password) <= 1024:
            raise InvalidCredentialsError()
        user = await self.user_reader.find_by_login_id(login_id)
        if user is None:
            # 없는 계정도 해싱 비용을 거쳐 즉시 실패 응답으로 계정 유무를 드러내지 않는다.
            await self.password_hasher.hash(password)
            raise InvalidCredentialsError()
        matches = await self.password_hasher.verify(password, user.password_hash)
        if not matches or not user.is_active:
            raise InvalidCredentialsError()
        session = LoginSession(
            uuid4(), user.id,
            datetime.now(timezone.utc) + timedelta(seconds=self.refresh_ttl_seconds),
        )
        refresh_token = self.refresh_codec.generate()
        await self.sessions.create(session, self.refresh_codec.digest(refresh_token))
        result = self._issue_pair(session, refresh_token)
        await self.transaction.commit()
        return result

    def _issue_pair(self, session: LoginSession, refresh_token: str) -> TokenPair:
        access = self.token_codec.issue(session.user_id, session.id)
        remaining = max(0, int((session.expires_at - datetime.now(timezone.utc)).total_seconds()))
        return TokenPair(access.access_token, refresh_token, access.expires_in, remaining)

    async def refresh(self, token: str) -> TokenPair:
        token_hash = self.refresh_codec.digest(token)
        state = await self.sessions.find_refresh_for_update(token_hash)
        now = datetime.now(timezone.utc)
        if state is None or state.session.revoked_at is not None or state.session.expires_at <= now:
            raise InvalidTokenError()
        if state.used_at is not None:
            # 재사용 차단은 인증 실패에 따른 rollback보다 먼저 확정한다.
            await self.sessions.revoke(state.session.id, now)
            await self.transaction.commit()
            self._cache_revoked(state.session)
            raise InvalidTokenError()
        user = await self.user_reader.find_by_id(state.session.user_id)
        if user is None or not user.is_active:
            await self.sessions.revoke(state.session.id, now)
            await self.transaction.commit()
            self._cache_revoked(state.session)
            raise InvalidTokenError()
        refresh_token = self.refresh_codec.generate()
        await self.sessions.rotate(
            state.session.id, token_hash, self.refresh_codec.digest(refresh_token), now,
        )
        result = self._issue_pair(state.session, refresh_token)
        await self.transaction.commit()
        return result

    async def authenticate(self, token: str) -> TokenClaims:
        claims = self.token_codec.decode(token)
        if self.revoked_sessions is not None and self.revoked_sessions.contains(claims.session_id):
            raise InvalidTokenError()
        session = await self.sessions.find(claims.session_id)
        if (session is None or session.user_id != claims.user_id
                or session.revoked_at is not None
                or session.expires_at <= datetime.now(timezone.utc)):
            raise InvalidTokenError()
        claims = replace(claims, session_expires_at=session.expires_at)
        user = await self.user_reader.find_by_id(claims.user_id)
        if user is None or not user.is_active:
            raise InvalidTokenError()
        return claims

    async def logout(self, token: str) -> None:
        # 서명과 만료는 검증하되 이미 폐기한 세션의 로그아웃도 재시도할 수 있다.
        claims = self.token_codec.decode(token)
        session = await self.sessions.find(claims.session_id)
        if session is None or session.user_id != claims.user_id:
            raise InvalidTokenError()
        user = await self.user_reader.find_by_id(claims.user_id)
        if user is None:
            raise InvalidTokenError()
        await self.sessions.revoke(claims.session_id, datetime.now(timezone.utc))
        await self.transaction.commit()
        self._cache_revoked(session)

    async def logout_session(self, refresh_token: str) -> None:
        state = await self.sessions.find_refresh_for_update(self.refresh_codec.digest(refresh_token))
        if state is None:
            raise InvalidTokenError()
        await self.sessions.revoke(state.session.id, datetime.now(timezone.utc))
        await self.transaction.commit()
        self._cache_revoked(state.session)

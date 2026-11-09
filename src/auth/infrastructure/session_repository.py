from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth.application.dto import LoginSession, RefreshState
from auth.infrastructure.models import LoginSessionModel, RefreshTokenModel


def _session(row: LoginSessionModel) -> LoginSession:
    return LoginSession(row.id, row.user_id, row.expires_at, row.revoked_at)


class SqlAlchemySessionRepository:
    def __init__(self, session: AsyncSession):
        self._db = session

    async def create(self, session: LoginSession, token_hash: str) -> None:
        self._db.add(LoginSessionModel(
            id=session.id, user_id=session.user_id, expires_at=session.expires_at,
        ))
        await self._db.flush()
        self._db.add(RefreshTokenModel(token_hash=token_hash, session_id=session.id))

    async def find(self, session_id: UUID) -> LoginSession | None:
        row = await self._db.get(LoginSessionModel, session_id, populate_existing=True)
        return _session(row) if row else None

    async def find_refresh_for_update(self, token_hash: str) -> RefreshState | None:
        session_id = await self._db.scalar(
            select(RefreshTokenModel.session_id).where(RefreshTokenModel.token_hash == token_hash)
        )
        if session_id is None:
            return None
        row = await self._db.scalar(
            select(LoginSessionModel).where(LoginSessionModel.id == session_id)
            .with_for_update().execution_options(populate_existing=True)
        )
        if row is None:
            return None
        # 잠금을 기다리는 동안 다른 요청이 토큰을 사용했을 수 있으므로 다시 읽는다.
        token = await self._db.get(RefreshTokenModel, token_hash, populate_existing=True)
        return RefreshState(_session(row), token.used_at)

    async def rotate(
        self, session_id: UUID, old_hash: str, new_hash: str, used_at: datetime
    ) -> None:
        old = await self._db.get(RefreshTokenModel, old_hash)
        old.used_at = used_at
        self._db.add(RefreshTokenModel(token_hash=new_hash, session_id=session_id))

    async def revoke(self, session_id: UUID, now: datetime) -> None:
        row = await self._db.scalar(
            select(LoginSessionModel).where(LoginSessionModel.id == session_id)
            .with_for_update().execution_options(populate_existing=True)
        )
        if row is not None and row.revoked_at is None:
            row.revoked_at = now

    async def revoke_all_for_user(self, user_id: int, now: datetime) -> None:
        await self._db.execute(update(LoginSessionModel).where(
            LoginSessionModel.user_id == user_id, LoginSessionModel.revoked_at.is_(None)
        ).values(revoked_at=now))

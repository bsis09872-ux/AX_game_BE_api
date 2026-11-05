# PostgreSQL의 유일 제약으로 같은 토큰의 동시 로그아웃을 멱등 처리한다.
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from auth.application.contracts import RevokedTokenRepository, TokenClaims
from auth.infrastructure.models import RevokedTokenModel


class SqlAlchemyRevokedTokenRepository(RevokedTokenRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def contains(self, jti: UUID) -> bool:
        result = await self._session.scalar(
            select(RevokedTokenModel.jti).where(RevokedTokenModel.jti == jti)
        )
        return result is not None

    async def revoke(self, claims: TokenClaims) -> None:
        statement = insert(RevokedTokenModel).values(
            jti=claims.jti, user_id=claims.user_id, expires_at=claims.expires_at
        ).on_conflict_do_nothing(index_elements=[RevokedTokenModel.jti])
        await self._session.execute(statement)

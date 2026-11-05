"""DB 연결 공통 모듈

- Base: 모든 도메인 ORM 모델의 부모
- get_session: 요청마다 AsyncSession을 열고 닫는 FastAPI 의존성

TODO: 설정 관리(config/.env) 방식이 정해지면 DATABASE_URL 읽는 부분을 옮긴다.
"""
import os
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/ax_game",
)

engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncIterator[AsyncSession]:
    # commit은 쓰기 서비스가 직접 한다. 예외가 나면 여기서 rollback만 보장한다.
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

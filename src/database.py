import os
from collections.abc import AsyncIterator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

project_root = Path(__file__).resolve().parents[1]
load_dotenv(project_root / ".env.local")
load_dotenv(project_root / ".env")
engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


# 각 도메인의 ORM 모델이 이 클래스를 상속하면 테이블 정의가 Base.metadata에 모인다.
class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncIterator[AsyncSession]:
    # commit은 유스케이스가 결정하고, 요청 처리 중 예외가 발생하면 미확정 변경을 되돌린다.
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from database import Base, engine
from shared.core.exception_handlers import register_exception_handlers
from shared.core.logging_config import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    try:
        # 시작 시점까지 등록된 ORM 모델의 테이블을 준비한다.
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield
    finally:
        await engine.dispose()


app = FastAPI(title="AX Game BE API", lifespan=lifespan)
register_exception_handlers(app)


@app.get("/health")
async def health():
    return {"status": "ok"}

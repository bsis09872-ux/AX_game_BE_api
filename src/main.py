from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from database import Base, engine

# 모델 등록 대비 주석 / 공통 모듈 생성 시 삭제하고 메인에서 사용 시 활성화한다.
# import users.infrastructure.models
# import inventory.infrastructure.models

from shared.core.exception_handlers import register_exception_handlers
from shared.core.logging_config import setup_logging

# create_all이 테이블을 만들도록 ORM 모델을 Base.metadata에 등록한다
import users.infrastructure.models  # noqa: F401
import wallet.infrastructure.models  # noqa: F401

# auth의 가입 흐름 완성 후 아래 import와 include_router 예시를 활성화한다.
# from auth.presentation.router import router as auth_router

API_PREFIX = "/v1"


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

# 도메인 라우터는 /auth 등의 경로를 선언하고 앱에 직접 등록할 때 공통 버전을 적용한다.
# 예: auth_router의 /auth + /register가 /v1/auth/register로 등록된다.
# app.include_router(auth_router, prefix=API_PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok"}

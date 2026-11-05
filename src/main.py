from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from database import Base, engine
from shared.core.exception_handlers import register_exception_handlers
from shared.core.logging_config import setup_logging

# auth의 가입 흐름 완성 후 아래 import와 include_router 예시를 활성화한다.
# from auth.presentation.router import router as auth_router


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

# 도메인 라우터는 /auth 등의 경로만 선언하고, 공통 버전은 여기서 적용한다.
api_router = APIRouter(prefix="/v1")
# 완성된 도메인 라우터는 아래 앱 등록 전에 api_router.include_router(...)로 연결한다.
# 예: auth_router의 /auth + /register가 /v1/auth/register로 등록된다.
# api_router.include_router(auth_router)
app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}

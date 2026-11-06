from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from database import Base, engine
from shared.core.exception_handlers import register_exception_handlers
from shared.core.logging_config import setup_logging

from auth.wiring import initialize_auth
from auth.presentation.dependencies import get_current_user_id
from auth.presentation.exception_handlers import register_auth_exception_handlers
from auth.presentation.router import router as auth_router
from users.presentation.router import create_user_router
from users.presentation.web_router import create_user_web_router
from auth.presentation.web_router import router as auth_web_router
from auth.presentation.web_dependencies import (
    get_current_web_user_id, get_web_settings, register_web_auth_handlers,
)

API_PREFIX = "/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    try:
        # 잘못된 인증 설정으로 요청을 받지 않도록 시작할 때 검증한다.
        initialize_auth()
        get_web_settings()
        # 시작 시점까지 등록된 ORM 모델의 테이블을 준비한다.
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield
    finally:
        await engine.dispose()


app = FastAPI(title="AX Game BE API", lifespan=lifespan)
app.state.templates = Jinja2Templates(directory="src/templates")
app.mount("/static", StaticFiles(directory="src/static"), name="static")

register_exception_handlers(app)
register_auth_exception_handlers(app)
register_web_auth_handlers(app)

# 도메인 라우터는 /auth 등의 경로를 선언하고 앱에 직접 등록할 때 공통 버전을 적용한다.
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(create_user_router(get_current_user_id), prefix=API_PREFIX)
app.include_router(auth_web_router)
app.include_router(create_user_web_router(get_current_web_user_id))


@app.get("/health")
async def health():
    return {"status": "ok"}

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import Base, engine

# 모델 등록 대비 주석 / 공통 모듈 생성 시 삭제하고 메인에서 사용 시 활성화한다.
# import users.infrastructure.models
# import inventory.infrastructure.models

from shared.core.exception_handlers import register_exception_handlers
from shared.core.logging_config import setup_logging

# create_all이 테이블을 만들도록 ORM 모델을 Base.metadata에 등록한다
import users.infrastructure.models  # noqa: F401
import wallet.infrastructure.models  # noqa: F401

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


app = FastAPI(title="Catch&Bid", lifespan=lifespan)

# 실행 폴더와 관계없이 src 아래의 공통 화면과 정적 파일을 찾는다.
SRC_DIR = Path(__file__).resolve().parent
app.state.templates = Jinja2Templates(directory=str(SRC_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(SRC_DIR / "static")), name="static")

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

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import Base, engine
from shared.core.exception_handlers import register_exception_handlers
from shared.core.logging_config import setup_logging

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

# 실행 폴더와 관계없이 src 아래의 공통 화면과 정적 파일을 찾는다.
SRC_DIR = Path(__file__).resolve().parent
app.state.templates = Jinja2Templates(directory=str(SRC_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(SRC_DIR / "static")), name="static")

register_exception_handlers(app)

# 도메인 라우터는 /auth 등의 경로를 선언하고 앱에 직접 등록할 때 공통 버전을 적용한다.
# 예: auth_router의 /auth + /register가 /v1/auth/register로 등록된다.
# app.include_router(auth_router, prefix=API_PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok"}

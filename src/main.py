from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Path as PathParameter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import Base, engine

from shared.core.exception_handlers import register_exception_handlers
from shared.core.logging_config import setup_logging

from auth.wiring import initialize_auth
from auth.presentation.dependencies import get_current_user_id, get_member_admin_service
from auth.presentation.exception_handlers import register_auth_exception_handlers
from auth.presentation.router import router as auth_router
from users.presentation.router import create_user_router
from users.presentation.web_router import create_user_web_router
from users.presentation.admin_router import create_member_admin_router
from users.infrastructure.schema import upgrade_member_controls
from auth.presentation.web_router import router as auth_web_router
from inventory.presentation.router import router as inventory_router
from inventory.presentation.dependencies import get_inventory_service
from auth.presentation.admin_router import create_admin_router
from auth.presentation.admin_auction_router import create_admin_auction_router
from auth.presentation.dependencies import get_admin_auction_reader
from shared.item_images import image_directory
from auth.presentation.web_dependencies import (
    get_current_web_user_id, get_current_web_admin_id, get_web_settings, register_web_auth_handlers,
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
            await upgrade_member_controls(connection)
        yield
    finally:
        await engine.dispose()


app = FastAPI(title="Catch&Bid", lifespan=lifespan)

# 실행 폴더와 관계없이 src 아래의 공통 화면과 정적 파일을 찾는다.
SRC_DIR = Path(__file__).resolve().parent
app.state.templates = Jinja2Templates(directory=str(SRC_DIR / "templates"))


@app.get('/static/sprites/item_upload_{image_id}.png', include_in_schema=False)
async def uploaded_item_image(image_id: str = PathParameter(pattern=r'^[0-9a-f]{32}$')):
    path = image_directory() / f'upload_{image_id}.png'
    if not path.is_file():
        raise HTTPException(404, '이미지를 찾을 수 없습니다.')
    return FileResponse(path, media_type='image/png', headers={
        'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'public, max-age=31536000, immutable',
    })


app.mount("/static", StaticFiles(directory=str(SRC_DIR / "static")), name="static")

register_exception_handlers(app)
register_auth_exception_handlers(app)
register_web_auth_handlers(app)

# 도메인 라우터는 /auth 등의 경로를 선언하고 앱에 직접 등록할 때 공통 버전을 적용한다.
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(create_user_router(get_current_user_id), prefix=API_PREFIX)
app.include_router(inventory_router, prefix=API_PREFIX)
app.include_router(auth_web_router)
app.include_router(create_admin_router(get_inventory_service))
app.include_router(create_admin_auction_router(get_admin_auction_reader))
app.include_router(create_member_admin_router(get_current_web_admin_id, get_member_admin_service))
app.include_router(create_user_web_router(get_current_web_user_id))


@app.get("/health")
async def health():
    return {"status": "ok"}

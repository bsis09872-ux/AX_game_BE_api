# region 표준 라이브러리 import
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
# endregion


# region 웹 프레임워크 import
from fastapi import FastAPI, HTTPException, Path as PathParameter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
# endregion


# region 데이터베이스 import
from database import Base, engine
# endregion


# region 공통 import
from shared.core.exception_handlers import register_exception_handlers
from shared.core.logging_config import setup_logging
from shared.core.http_application import HttpApplication
from shared.core.http_settings import read_cors_origins
from shared.core.openapi import (
    OPENAPI_DESCRIPTION, OPENAPI_TAGS, SWAGGER_UI_PARAMETERS, install_openapi, read_docs_urls,
)
from shared.item_images import image_directory
from composition import get_admin_auction_queries, get_member_admin_service
from web_router import create_dashboard_router
# endregion


# region 도메인 import: 인증
from auth.wiring import initialize_auth
from auth.presentation.dependencies import get_current_user_id
from auth.presentation.exception_handlers import register_auth_exception_handlers
from auth.presentation.router import router as auth_router
from auth.presentation.web_router import router as auth_web_router
from auth.presentation.web_dependencies import (
    get_current_web_user_id, get_current_web_admin_id, get_web_settings, register_web_auth_handlers,
    require_web_origin,  # 경매 화면의 POST 출처 확인
)
# endregion


# region 도메인 import: 유저
from users.presentation.router import create_user_router
from users.presentation.web_router import create_user_web_router
from users.presentation.admin_router import create_member_admin_router
from users.infrastructure.schema import upgrade_member_controls
# endregion


# region 도메인 import: 인벤토리
from inventory.presentation.admin_router import create_inventory_admin_router
from inventory.presentation.router import router as inventory_router
from inventory.presentation.dependencies import get_inventory_service
from inventory.presentation.web_router import create_inventory_web_router
from inventory.wiring import is_fishing_enabled
from client.web_router import create_client_web_router, create_fishing_api_router, create_opening_router
from world.presentation.router import router as world_router
# endregion


# region 도메인 import: 지갑
from wallet.presentation.router import create_wallet_router
from wallet.presentation.web_router import create_wallet_web_router
from auction.wiring import build_held_amount_reader  # 지갑 예약금 조회 (경매 제공 AuctionHeldAmountReader)
# endregion

# region 도메인 import: 경매
from auction.presentation.admin_router import create_admin_auction_router
from auction.presentation.listings.admin_web_router import create_listing_admin_web_router
from auction.presentation.listings.router import router as listing_router
from auction.presentation.trades.router import router as trade_router
from auction.wiring import build_auction_scheduler, wire_auction_dependencies
# endregion


# region 도메인 모델 등록
# create_all이 테이블을 만들도록 ORM 모델을 Base.metadata에 등록한다.
import auth.infrastructure.models  # noqa: F401
import users.infrastructure.models  # noqa: F401
import inventory.infrastructure.models  # noqa: F401
import wallet.infrastructure.models  # noqa: F401
import auction.infrastructure.listings.models  # noqa: F401 (임시)
import world.infrastructure.models  # noqa: F401
# endregion


# region 경매·가방 화면
from auction.presentation.web_router import create_auction_web_router
from auction.presentation.web_dependencies import read_wallet_box
# endregion
API_PREFIX = "/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    # 경매 마감 스케줄러: 5초마다 마감된 매물을 정산·유찰하고 다음 매물을 공개한다.
    auction_scheduler = build_auction_scheduler()
    try:
        # 잘못된 인증 설정으로 요청을 받지 않도록 시작할 때 검증한다.
        initialize_auth()
        get_web_settings()
        # 시작 시점까지 등록된 ORM 모델의 테이블을 준비한다.
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await upgrade_member_controls(connection)
        # 테이블 준비가 끝난 뒤 시작해야 없는 테이블을 조회하지 않는다.
        auction_scheduler.start()
        yield
    finally:
        # DB 연결을 닫기 전에 스케줄러를 먼저 멈춘다. 시작 전에 실패했어도 안전하다.
        await auction_scheduler.stop()
        await engine.dispose()

app = HttpApplication(
    title="Catch&Bid", lifespan=lifespan, cors_origins=read_cors_origins(),
    description=OPENAPI_DESCRIPTION, openapi_tags=OPENAPI_TAGS,
    swagger_ui_parameters=SWAGGER_UI_PARAMETERS,
    **read_docs_urls(),  # DOCS_ENABLED=false 이면 /docs를 끈다
)

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


# 브라우저는 탭 아이콘을 /favicon.ico로도 요청한다. 같은 파일을 돌려줘서 404를 막는다.
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(
        SRC_DIR / "static" / "favicon" / "favicon.ico",
        media_type="image/x-icon",
        headers={"Cache-Control": "public, max-age=86400"},
    )


app.mount("/static", StaticFiles(directory=str(SRC_DIR / "static")), name="static")

register_exception_handlers(app)
register_auth_exception_handlers(app)
register_web_auth_handlers(app)

# 도메인 라우터는 /auth 등의 경로를 선언하고 앱에 직접 등록할 때 공통 버전을 적용한다.


# region 도메인 라우터: 인증
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(auth_web_router)
# endregion


# region 도메인 라우터: 유저
app.include_router(create_user_router(get_current_user_id), prefix=API_PREFIX)
app.include_router(create_user_web_router(get_current_web_user_id))
# endregion


# region 도메인 라우터: 인벤토리
app.include_router(inventory_router, prefix=API_PREFIX)
if is_fishing_enabled():
    app.include_router(create_fishing_api_router(get_current_user_id), prefix=API_PREFIX)
# 가방 화면에 지갑 박스 읽기 함수를 넘긴다 (인벤토리가 wallet을 import하지 않게 main이 연결)
app.include_router(create_inventory_web_router(get_current_web_user_id, read_wallet_box))
# endregion


# region 도메인 라우터: 지갑
app.include_router(create_wallet_router(get_current_user_id, build_held_amount_reader), prefix=API_PREFIX)
app.include_router(create_wallet_web_router(get_current_web_user_id, build_held_amount_reader))
# endregion


# region 관리자 화면
app.include_router(create_dashboard_router(get_current_web_admin_id))
app.include_router(create_inventory_admin_router(get_current_web_admin_id, get_inventory_service))
app.include_router(create_admin_auction_router(get_current_web_admin_id, get_admin_auction_queries))
app.include_router(create_member_admin_router(get_current_web_admin_id, get_member_admin_service))
app.include_router(create_listing_admin_web_router(get_current_web_admin_id))
# endregion


wire_auction_dependencies(app, get_current_user_id)
app.include_router(listing_router, prefix=API_PREFIX)
app.include_router(trade_router, prefix=API_PREFIX)
# 경매 화면(목록·상세·등록·입찰·취소·내 거래). 로그인과 출처 확인은 auth 함수를 넘긴다
app.include_router(create_auction_web_router(get_current_web_user_id, require_web_origin))

app.include_router(create_client_web_router(
    get_current_web_user_id, require_web_origin, is_fishing_enabled,
), prefix=API_PREFIX)
app.include_router(world_router)
app.include_router(create_opening_router())


@app.get("/health", tags=["system"], summary="서버 상태 확인")
async def health():
    return {"status": "ok"}


# 모든 라우터를 등록한 뒤 호출한다: Swagger에서 화면 경로를 숨기고 공통 오류 응답을 붙인다
install_openapi(app)

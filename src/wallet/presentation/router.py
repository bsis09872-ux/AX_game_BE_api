"""지갑·거래 라우터 (WALL-01, 04, 05)

경로: GET /v1/wallets/me, GET /v1/users/me/trades, GET /v1/trades/{trade_id}
내 거래 목록은 /trades/me가 아니라 /users/me/trades다. /trades/{trade_id}와 자리를 다투지 않는다.

외부 API만 둔다. WALL-06·07·08은 내부 함수라 라우터가 없다.
라우터는 얇게 유지한다: 인증된 사용자 ID와 세션을 받아 서비스에 넘기고,
서비스가 던진 도메인 예외는 공통 핸들러가 detail.code/message로 바꾼다.

main.py 등록:
    from wallet.presentation.router import router as wallet_router
    app.include_router(wallet_router)
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

# TODO: auth 담당 쪽에 get_current_user_id(HTTPBearer + 폐기 토큰·탈퇴 검사, int 반환)가 생기면 동작한다.
#       그 전까지 main.py에 이 라우터를 등록하지 않는다.
from auth.presentation.dependencies import get_current_user_id
from shared.core.database import get_session
from shared.core.schemas import PageParams, PageResponse
from wallet.application import service

from .schemas import TradeDetailResponse, TradeListItem, WalletResponse

router = APIRouter(prefix="/v1", tags=["wallet"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserIdDep = Annotated[int, Depends(get_current_user_id)]


@router.get(
    "/wallets/me",
    response_model=WalletResponse,
    summary="[WALL-01] 내 지갑 조회",
    responses={404: {"description": "WALLET_NOT_FOUND"}},
)
async def get_my_wallet(session: SessionDep, user_id: UserIdDep) -> WalletResponse:
    return await service.get_my_wallet(session, user_id=user_id)


@router.get(
    "/users/me/trades",
    response_model=PageResponse[TradeListItem],
    summary="[WALL-04] 내 거래 내역 조회",
)
async def list_my_trades(
    session: SessionDep,
    user_id: UserIdDep,
    page: Annotated[PageParams, Depends()],
    role: Literal["buy", "sell", "all"] = "all",
) -> PageResponse[TradeListItem]:
    # role 값이 셋 중 하나가 아니면 FastAPI가 422 → 공통 핸들러가 VALIDATION_ERROR로 변환
    return await service.list_my_trades(session, user_id=user_id, role=role, page=page)


@router.get(
    "/trades/{trade_id}",
    response_model=TradeDetailResponse,
    summary="[WALL-05] 거래 상세 조회",
    responses={
        404: {"description": "TRADE_NOT_FOUND (없는 거래 또는 당사자가 아님)"},
    },
)
async def get_trade(
    session: SessionDep,
    user_id: UserIdDep,
    # 경로의 "15"는 int로 받는다. 숫자가 아니면 422(VALIDATION_ERROR)
    trade_id: Annotated[int, Path(ge=1, description="거래 ID (10진 숫자 문자열)")],
) -> TradeDetailResponse:
    return await service.get_trade_detail(session, user_id=user_id, trade_id=trade_id)

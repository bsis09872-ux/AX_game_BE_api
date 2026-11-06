"""지갑 라우터

경로(앱에서 /v1 prefix 적용 후):
  GET  /v1/wallets/me                 내 지갑 조회 (WALL-01)
  POST /v1/wallets/{user_id}/charge   관리자 지갑 충전

subtract_balance(입찰 차감)는 경매 쪽 내부 호출이라 라우터가 없다(wallet.wiring.build_wallet_service 사용).
라우터는 얇게 유지한다: 인증된 사용자 ID를 서비스에 넘기고 결과를 응답 스키마로 바꾼다.
서비스가 던진 도메인 예외는 공통 핸들러가 detail.code/message로 바꾼다.

main.py 등록 (auth의 get_current_user_id가 생긴 뒤):
    from wallet.presentation.router import router as wallet_router
    app.include_router(wallet_router, prefix=API_PREFIX)
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from wallet.application.service import WalletService

from .dependencies import get_wallet_service
from .schemas import ChargeRequest, WalletResponse

router = APIRouter(tags=["wallet"])

ServiceDep = Annotated[WalletService, Depends(get_wallet_service)]

SessionDep = Annotated[AsyncSession, Depends(get_db)]


@router.get(
    "/wallets/me",
    response_model=WalletResponse,
    summary="[WALL-01] 내 지갑 조회",
    responses={404: {"description": "WALLET_NOT_FOUND"}},
)
async def get_my_wallet(service: ServiceDep, user_id: UserIdDep) -> WalletResponse:
    return WalletResponse.model_validate(await service.get_my_wallet(user_id))


@router.post(
    "/wallets/{user_id}/charge",
    response_model=WalletResponse,
    summary="관리자 지갑 충전",
    responses={
        403: {"description": "INSUFFICIENT_AUTHORITY (관리자가 아님)"},
        404: {"description": "WALLET_NOT_FOUND"},
    },
)
async def charge_wallet(
    service: ServiceDep,
    session: SessionDep,
    user_id: Annotated[int, Path(ge=1, description="충전할 회원 ID")],
    body: ChargeRequest,
) -> WalletResponse:
    await service.add_balance(user_id, body.amount)
    await session.commit()
    # commit이 성공한 뒤에만 잔액 변경 로그를 남긴다 (balance_log.py 규칙)
    service.logger.flush()
    return WalletResponse.model_validate(await service.get_my_wallet(user_id))


# 거래 내역(WALL-04)·거래 상세(WALL-05)는 서비스에서 빠져 있어 라우터도 잠시 뺀다.
# 서비스에 list_my_trades / get_trade_detail이 다시 생기면 아래를 되살린다.
#
# from typing import Literal
# from .schemas import PageParams, PageResponse, TradeDetailResponse, TradeListItem
#
# @router.get(
#     "/users/me/trades",
#     response_model=PageResponse[TradeListItem],
#     summary="[WALL-04] 내 거래 내역 조회",
# )
# async def list_my_trades(
#     service: ServiceDep,
#     user_id: UserIdDep,
#     page: Annotated[PageParams, Depends()],
#     role: Literal["buy", "sell", "all"] = "all",
# ) -> PageResponse[TradeListItem]:
#     result = await service.list_my_trades(user_id, role=role, page=page.page, size=page.size)
#     return PageResponse[TradeListItem](
#         items=[TradeListItem.model_validate(row) for row in result.items],
#         page=result.page,
#         size=result.size,
#         total=result.total,
#     )
#
#
# @router.get(
#     "/trades/{trade_id}",
#     response_model=TradeDetailResponse,
#     summary="[WALL-05] 거래 상세 조회",
#     responses={404: {"description": "TRADE_NOT_FOUND (없는 거래 또는 당사자가 아님)"}},
# )
# async def get_trade(
#     service: ServiceDep,
#     user_id: UserIdDep,
#     trade_id: Annotated[int, Path(ge=1, description="거래 ID (10진 숫자 문자열)")],
# ) -> TradeDetailResponse:
#     return TradeDetailResponse.model_validate(await service.get_trade_detail(user_id, trade_id))

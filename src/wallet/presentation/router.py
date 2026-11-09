"""지갑 라우터

경로(앱에서 /v1 prefix 적용 후):
  GET  /v1/wallets/me                 내 지갑 조회 (WALL-01)
  POST /v1/wallets/{user_id}/charge   관리자 지갑 충전

subtract_balance·check_bid_funds·settle_sale은 경매 쪽 내부 호출이라 라우터가 없다(wallet.wiring.build_wallet_service 사용).
라우터는 얇게 유지한다: 인증된 사용자 ID를 서비스에 넘기고 결과를 응답 스키마로 바꾼다.
서비스가 던진 도메인 예외는 공통 핸들러가 detail.code/message로 바꾼다.

인증 함수는 auth를 import하지 않고 바깥(main.py)에서 주입받는다 (users 라우터와 같은 방식):
    from wallet.presentation.router import create_wallet_router
    app.include_router(create_wallet_router(get_current_user_id), prefix=API_PREFIX)
"""
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Path

from wallet.application.service import WalletService

from .dependencies import SessionDep, get_wallet_service
from .schemas import ChargeRequest, WalletResponse

ServiceDep = Annotated[WalletService, Depends(get_wallet_service)]


def create_wallet_router(current_user_id: Callable[..., Awaitable[int]]) -> APIRouter:
    """current_user_id: 토큰을 검증해 인증된 회원 ID를 돌려주는 의존성 (auth의 get_current_user_id)"""
    router = APIRouter(tags=["wallet"])
    UserIdDep = Annotated[int, Depends(current_user_id)]

    @router.get(
        "/wallets/me",
        response_model=WalletResponse,
        summary="[WALL-01] 내 지갑 조회",
        responses={401: {"description": "인증 필요"}},
    )
    async def get_my_wallet(service: ServiceDep, session: SessionDep, user_id: UserIdDep) -> WalletResponse:
        view = await service.get_my_wallet(user_id)
        # 처음 조회라 지갑을 만들었다면 확정한다 (이미 있었으면 바뀐 것이 없다)
        await session.commit()
        # commit이 성공한 뒤에만 INITIAL_GRANT 로그를 남긴다 (infrastructure/balance_log.py 규칙)
        service.logger.flush()
        return WalletResponse.model_validate(view)

    @router.post(
        "/wallets/{user_id}/charge",
        response_model=WalletResponse,
        summary="관리자 지갑 충전",
        responses={
            401: {"description": "인증 필요"},
            403: {"description": "INSUFFICIENT_AUTHORITY (관리자가 아님)"},
            404: {"description": "WALLET_NOT_FOUND (없는 회원)"},
        },
    )
    async def charge_wallet(
        service: ServiceDep,
        session: SessionDep,
        actor_id: UserIdDep,
        user_id: Annotated[int, Path(ge=1, description="충전할 회원 ID")],
        body: ChargeRequest,
    ) -> WalletResponse:
        # 관리자 여부는 서비스(RoleCheck)가 판단한다. 라우터는 요청자 ID만 넘긴다.
        await service.add_balance(actor_id, user_id, body.amount)
        await session.commit()
        # commit이 성공한 뒤에만 잔액 변경 로그를 남긴다 (infrastructure/balance_log.py 규칙)
        service.logger.flush()
        return WalletResponse.model_validate(await service.get_my_wallet(user_id))

    return router


# 거래 내역(WALL-04)·거래 상세(WALL-05)는 서비스에서 빠져 있어 라우터도 잠시 뺀다.
# 서비스에 list_my_trades / get_trade_detail이 다시 생기면 아래를 되살린다.
# 되살릴 때는 create_wallet_router 안으로 옮긴다 (@router와 UserIdDep는 함수 안에서 정의된다).
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

"""지갑 라우터

경로(앱에서 /v1 prefix 적용 후):
  GET  /v1/wallets/me                 내 지갑 조회 (WALL-02)
  POST /v1/wallets/{user_id}/charge   관리자 지갑 충전 (WALL-01)

subtract_balance·check_bid_funds·settle_sale은 경매 쪽 내부 호출이라 라우터가 없다(wallet.wiring.build_wallet_service 사용).
라우터는 얇게 유지한다: 인증된 사용자 ID를 서비스에 넘기고 결과를 응답 스키마로 바꾼다.
서비스가 던진 도메인 예외는 공통 핸들러가 detail.code/message로 바꾼다.

다른 도메인 기능은 import하지 않고 바깥(main.py)에서 주입받는다 (users 라우터와 같은 방식):
    from wallet.presentation.router import create_wallet_router
    app.include_router(create_wallet_router(get_current_user_id, build_held_reader), prefix=API_PREFIX)
"""
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Path

from wallet.application.service import WalletService

from .dependencies import HeldReaderBuilder, SessionDep, wallet_service_dependency
from .schemas import BIGINT_MAX, ChargeRequest, WalletResponse


def create_wallet_router(
    current_user_id: Callable[..., Awaitable[int]],
    build_held_reader: HeldReaderBuilder,
) -> APIRouter:
    """지갑 API 라우터를 만든다.

    current_user_id: 토큰을 검증해 인증된 회원 ID를 돌려주는 의존성 (auth의 get_current_user_id)
    build_held_reader: 요청 세션으로 예약 금액 조회기(HeldAmountReader)를 만드는 함수 (경매 제공)
    """
    router = APIRouter(tags=["wallet"])
    UserIdDep = Annotated[int, Depends(current_user_id)]
    ServiceDep = Annotated[WalletService, Depends(wallet_service_dependency(build_held_reader))]

    @router.get(
        "/wallets/me",
        response_model=WalletResponse,
        summary="[WALL-02] 내 지갑 조회",
        responses={401: {"description": "인증 필요"}},
    )
    async def get_my_wallet(service: ServiceDep, session: SessionDep, user_id: UserIdDep) -> WalletResponse:
        view = await service.get_my_wallet(user_id)
        # 처음 조회라 지갑을 만들었다면 확정한다 (이미 있었으면 바뀐 것이 없다)
        # INITIAL_GRANT 로그는 commit 성공 시 세션 이벤트로 자동으로 남는다 (balance_recoder.py)
        await session.commit()
        return WalletResponse.model_validate(view)

    @router.post(
        "/wallets/{user_id}/charge",
        response_model=WalletResponse,
        summary="[WALL-01] 관리자 지갑 충전",
        responses={
            400: {"description": "BALANCE_LIMIT_EXCEEDED (충전 후 잔액이 BIGINT 최대값을 넘음)"},
            401: {"description": "인증 필요"},
            403: {"description": "INSUFFICIENT_AUTHORITY (관리자가 아님)"},
            404: {"description": "WALLET_NOT_FOUND (없는 회원)"},
        },
    )
    async def charge_wallet(
        service: ServiceDep,
        session: SessionDep,
        actor_id: UserIdDep,
        user_id: Annotated[int, Path(ge=1, le=BIGINT_MAX, description="충전할 회원 ID")],
        body: ChargeRequest,
    ) -> WalletResponse:
        # 관리자 여부는 서비스(RoleCheck)가 판단한다. 라우터는 요청자 ID만 넘긴다.
        await service.add_balance(actor_id, user_id, body.amount)
        # 응답까지 만든 뒤 commit한다. 응답 조회가 실패하면 충전도 함께 rollback된다.
        view = await service.get_my_wallet(user_id)
        # 잔액 변경 로그는 commit 성공 시 세션 이벤트로 자동으로 남는다 (balance_recoder.py)
        await session.commit()
        return WalletResponse.model_validate(view)

    return router

"""지갑 화면 라우터 (GET /wallet, Jinja2)

- 로그인 확인(현재 사용자 번호)은 main.py에서 넘겨 받는다 (auth의 쿠키 구조를 모른다).
  웹 화면이라 API용 get_current_user_id가 아니라 쿠키용 get_current_web_user_id를 넘긴다.
- 서비스의 내 지갑 조회(WALL-02)를 그대로 쓰고, 화면에는 응답 모델(WalletResponse)의 공개 값만 넘긴다.
- 처음 조회면 지갑을 만들고 초기 골드를 지급하므로(WALL-06 지연 생성) API 라우터와 같이 commit한다.
  INITIAL_GRANT 로그는 commit 성공 시 세션 이벤트로 자동으로 남는다 (balance_recoder.py).
- 개인 화면이라 브라우저에 저장하지 않게 한다 (Cache-Control: no-store).
"""
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from wallet.application.service import WalletService

from .dependencies import HeldReaderBuilder, SessionDep, wallet_service_dependency
from .schemas import WalletResponse


def create_wallet_web_router(
    current_user_id: Callable[..., Awaitable[int]],
    build_held_reader: HeldReaderBuilder,
) -> APIRouter:
    """지갑 화면 라우터를 만든다.

    current_user_id: 로그인 쿠키를 확인해 회원 ID를 돌려주는 의존성 (auth의 get_current_web_user_id)
    build_held_reader: 요청 세션으로 예약 금액 조회기를 만드는 함수 (경매 제공, API 라우터와 같은 것)
    """
    router = APIRouter(tags=["wallet-web"])
    get_wallet_service = wallet_service_dependency(build_held_reader)

    @router.get("/wallet", response_class=HTMLResponse)
    async def get_wallet_page(
        request: Request,
        session: SessionDep,
        user_id: int = Depends(current_user_id),
        service: WalletService = Depends(get_wallet_service),
    ) -> HTMLResponse:
        view = await service.get_my_wallet(user_id)
        await session.commit()

        response = request.app.state.templates.TemplateResponse(
            request=request,
            name="wallet/index.html",
            context={"wallet": WalletResponse.model_validate(view)},
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    return router

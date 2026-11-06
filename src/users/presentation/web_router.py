from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from users.application.service import UserService
from users.presentation.dependencies import get_user_service
from users.presentation.schemas import UserMeResponse


def create_user_web_router(
    current_user_id: Callable[..., Awaitable[int]],
) -> APIRouter:
    # 실제 인증 구현은 main에서 전달한다. users는 auth의 쿠키나 토큰 구조를 참조하지 않는다.
    router = APIRouter()

    @router.get("/me", response_class=HTMLResponse)
    async def get_me_page(
        request: Request,
        user_id: int = Depends(current_user_id),
        service: UserService = Depends(get_user_service),
    ) -> HTMLResponse:
        # 의존성이 인증한 본인 ID로 조회하고 화면에 공개할 필드만 응답 데이터로 만든다.
        user = await service.get_user(user_id=user_id)

        public_user = UserMeResponse.from_user(user)

        response = request.app.state.templates.TemplateResponse(
            request=request,
            name="users/me.html",
            context={"user": public_user},
        )

        # 개인정보 화면을 HTTP 캐시에 저장하지 않도록 한다.
        response.headers["Cache-Control"] = "no-store"

        return response

    return router

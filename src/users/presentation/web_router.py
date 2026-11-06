from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from users.application.service import UserService
from users.presentation.dependencies import get_user_service
from users.presentation.schemas import UserMeResponse


def create_user_web_router(
    current_user_id: Callable[..., Awaitable[int]],
) -> APIRouter:
    router = APIRouter()

    @router.get("/me", response_class=HTMLResponse)
    async def get_me_page(
        request: Request,
        user_id: int = Depends(current_user_id),
        service: UserService = Depends(get_user_service),
    ) -> HTMLResponse:
        user = await service.get_user(user_id=user_id)

        public_user = UserMeResponse.from_user(user)

        response = request.app.state.templates.TemplateResponse(
            request=request,
            name="users/me.html",
            context={"user": public_user},
        )

        response.headers["Cache-Control"] = "no-store"

        return response

    return router

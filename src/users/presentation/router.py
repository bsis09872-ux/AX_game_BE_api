from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, Response

from users.application.service import UserService
from users.presentation.dependencies import get_user_service
from users.presentation.schemas import UserMeResponse


def create_user_router(
    current_user_id: Callable[..., Awaitable[int]],
) -> APIRouter:
    router = APIRouter(prefix="/users", tags=["users"])

    @router.get("/me", response_model=UserMeResponse)
    async def get_me(
        response: Response,
        user_id: int = Depends(current_user_id),
        service: UserService = Depends(get_user_service),
    ) -> UserMeResponse:
        user = await service.get_user(user_id)
        response.headers["Cache-Control"] = "no-store"
        return UserMeResponse.from_user(user)

    return router

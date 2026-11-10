"""낚시 클라이언트의 화면과 쿠키 인증 연결부. 기존 서비스만 조합한다."""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import Literal
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.routing import APIRoute

from auth.presentation.web_dependencies import WebAuthenticationRequired
from inventory.presentation.schemas import InventoryItemResponse
from world.domain.rules import WorldError
from world.presentation.dependencies import WorldServiceDep
from world.presentation.schemas import CastRequest, CatchRequest


class ClientApiRoute(APIRoute):
    """화면 이동용 인증 예외를 클라이언트 API에서는 JSON 401로 전달한다."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request: Request):
            try:
                response = await handler(request)
            except WebAuthenticationRequired:
                response = JSONResponse(
                    status_code=401,
                    content={
                        "detail": {
                            "code": "UNAUTHORIZED",
                            "message": "로그인이 필요합니다.",
                        },
                    },
                )
            except HTTPException as error:
                response = JSONResponse(
                    status_code=error.status_code,
                    content={"detail": error.detail},
                    headers=error.headers,
                )
            except WorldError as error:
                response = JSONResponse(
                    status_code=error.status,
                    content={
                        "detail": {"code": error.code, "message": error.message},
                    },
                    headers={"Retry-After": str(error.retry_after)}
                    if error.retry_after
                    else None,
                )

            response.headers["Cache-Control"] = "no-store"
            return response

        return handle


def create_client_web_router(
    current_user_id: Callable[..., Awaitable[int]],
    require_origin: Callable,
    fishing_enabled: Callable[[], bool],
) -> APIRouter:
    router = APIRouter()

    @router.get(
        "/play", response_class=HTMLResponse, dependencies=[Depends(current_user_id)]
    )
    async def play(request: Request, map: Literal["world", "lake", "halloween"] = Query("world")):
        response = request.app.state.templates.TemplateResponse(
            request=request,
            name="game/play.html",
            context={"fishing_enabled": fishing_enabled(), "map_name": map},
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    api = APIRouter(route_class=ClientApiRoute)

    @api.post("/play/casts", dependencies=[Depends(require_origin)])
    async def begin_cast(
        values: CastRequest,
        service: WorldServiceDep,
        user_id: int = Depends(current_user_id),
    ):
        if not fishing_enabled():
            raise HTTPException(
                503,
                detail={
                    "code": "FISHING_DISABLED",
                    "message": "낚시 보상이 비활성화되어 있습니다.",
                },
            )
        return await service.begin_cast(user_id, values.connection_id, values.id)

    @api.post(
        "/play/casts/cancel", dependencies=[Depends(require_origin)], status_code=204
    )
    async def cancel_cast(
        values: CastRequest,
        service: WorldServiceDep,
        user_id: int = Depends(current_user_id),
    ):
        await service.cancel_cast(user_id, values.connection_id, values.id)

    @api.post(
        "/play/fishing-results",
        status_code=201,
        response_model=InventoryItemResponse,
        dependencies=[Depends(require_origin)],
    )
    async def catch_item(
        values: CatchRequest,
        service: WorldServiceDep,
        user_id: int = Depends(current_user_id),
    ):
        if not fishing_enabled():
            raise HTTPException(
                503,
                detail={
                    "code": "FISHING_DISABLED",
                    "message": "낚시 보상이 비활성화되어 있습니다.",
                },
            )

        return await service.catch(user_id, values.cast_id)

    router.include_router(api)
    return router


def create_fishing_api_router(current_user_id: Callable[..., Awaitable[int]]) -> APIRouter:
    """Bearer 진입점도 같은 cast 검증을 사용한다. 인증 의존성은 main에서 전달한다."""
    router = APIRouter(route_class=ClientApiRoute, tags=["fishing"])

    @router.post("/fishing-results", status_code=201, response_model=InventoryItemResponse)
    async def catch_item(
        values: CatchRequest,
        service: WorldServiceDep,
        user_id: int = Depends(current_user_id),
    ):
        return await service.catch(user_id, values.cast_id)

    return router


def create_opening_router() -> APIRouter:
    router = APIRouter()

    @router.get("/opening", response_class=HTMLResponse, include_in_schema=False)
    async def opening(request: Request):
        return request.app.state.templates.TemplateResponse(
            request=request, name="game/opening.html", context={},
        )

    return router

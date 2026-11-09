import csv
import io
import logging
import asyncio
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse

from auth.presentation.web_dependencies import get_current_web_admin_id
from inventory.application.service import InventoryService
from inventory.presentation.schemas import (
    AdminDefinitionResponse, DefinitionCreateRequest, DefinitionUpdateRequest,
    EventResponse, PageResponse,
)
from users.application.service import UserService
from users.presentation.dependencies import get_user_service
from users.presentation.schemas import UserMeResponse
from shared.item_images import MAX_UPLOAD_BYTES, list_images, save_image

logger = logging.getLogger(__name__)


def record_admin_action(user_id: int, action: str, target_id: int) -> None:
    logger.info("admin_action user_id=%s action=%s target_id=%s", user_id, action, target_id)


def csv_cell(value) -> str:
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text


def create_admin_router(inventory_dependency) -> APIRouter:
    """관리자 웹의 표현 계층. 카탈로그 업무는 기존 공개 서비스에 위임한다."""
    router = APIRouter(prefix="/admin", tags=["admin-web"])

    async def render_page(request, users, user_id, template, section, **context):
        user = UserMeResponse.from_user(await users.get_user(user_id))
        return request.app.state.templates.TemplateResponse(
            request=request, name=f'auth/admin/{template}.html',
            context={'user': user, 'section': section, **context},
            headers={'Cache-Control': 'no-store'},
        )

    @router.get('/item-images')
    async def available_images(response: Response, user_id: int = Depends(get_current_web_admin_id)):
        response.headers['Cache-Control'] = 'no-store'
        return await asyncio.to_thread(list_images)

    @router.post('/item-images', status_code=201)
    async def upload_image(request: Request, response: Response, user_id: int = Depends(get_current_web_admin_id)):
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_UPLOAD_BYTES:
                raise HTTPException(413, '이미지는 2MB 이하의 파일을 선택해 주세요.')
            data.extend(chunk)
        try:
            result = await asyncio.to_thread(save_image, bytes(data))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        response.headers['Cache-Control'] = 'no-store'
        return result

    @router.get("", response_class=HTMLResponse)
    async def dashboard(
        request: Request,
        user_id: int = Depends(get_current_web_admin_id),
        users: UserService = Depends(get_user_service),
    ):
        return await render_page(request, users, user_id, 'home', 'home')

    @router.get('/catalogs', response_class=HTMLResponse)
    async def catalog_page(request: Request, user_id: int = Depends(get_current_web_admin_id),
                           users: UserService = Depends(get_user_service)):
        return await render_page(request, users, user_id, 'catalogs', 'catalogs')

    @router.get('/catalogs/new', response_class=HTMLResponse)
    async def new_catalog_page(request: Request, user_id: int = Depends(get_current_web_admin_id),
                              users: UserService = Depends(get_user_service)):
        return await render_page(request, users, user_id, 'editor', 'editor', item=None)

    @router.get('/catalogs/{definition_id}/edit', response_class=HTMLResponse)
    async def edit_catalog_page(request: Request, definition_id: int = Path(ge=1),
                               user_id: int = Depends(get_current_web_admin_id),
                               users: UserService = Depends(get_user_service),
                               inventory: InventoryService = Depends(inventory_dependency)):
        item = AdminDefinitionResponse.from_info(await inventory.get_definition(definition_id))
        return await render_page(request, users, user_id, 'editor', 'editor', item=item.model_dump())

    @router.get('/history', response_class=HTMLResponse)
    async def history_page(request: Request, user_id: int = Depends(get_current_web_admin_id),
                           users: UserService = Depends(get_user_service)):
        return await render_page(request, users, user_id, 'events', 'events')

    @router.get("/item-catalogs", response_model=PageResponse[AdminDefinitionResponse])
    async def catalogs(
        response: Response,
        category: Literal["FISH", "GEM", "MISC"] | None = None,
        rarity: Literal["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY"] | None = None,
        sort: Literal["rarity_desc", "name_asc"] = "rarity_desc",
        page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
        user_id: int = Depends(get_current_web_admin_id),
        inventory: InventoryService = Depends(inventory_dependency),
    ):
        rows, total = await inventory.list_definitions(
            category=category, rarity=rarity, sort=sort, page=page, size=size,
        )
        response.headers["Cache-Control"] = "no-store"
        return PageResponse(items=[AdminDefinitionResponse.from_info(row) for row in rows],
                            total=total, page=page, size=size)

    @router.get("/item-catalogs/export.csv")
    async def export_catalogs(
        background_tasks: BackgroundTasks,
        category: Literal["FISH", "GEM", "MISC"] | None = None,
        rarity: Literal["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY"] | None = None,
        sort: Literal["rarity_desc", "name_asc"] = "rarity_desc",
        page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
        user_id: int = Depends(get_current_web_admin_id),
        inventory: InventoryService = Depends(inventory_dependency),
    ):
        rows, _ = await inventory.list_definitions(
            category=category, rarity=rarity, sort=sort, page=page, size=size,
        )
        values = [AdminDefinitionResponse.from_info(row).model_dump() for row in rows]

        def chunks():
            yield "\ufeff"
            stream = io.StringIO(newline="")
            fields = list(AdminDefinitionResponse.model_fields)
            writer = csv.writer(stream)
            writer.writerow(fields)
            yield stream.getvalue()
            for row in values:
                stream.seek(0)
                stream.truncate(0)
                writer.writerow([csv_cell(row[field]) for field in fields])
                yield stream.getvalue()

        background_tasks.add_task(record_admin_action, user_id, "catalog_export", page)
        return StreamingResponse(chunks(), media_type="text/csv; charset=utf-8",
                                 background=background_tasks, headers={
            "Content-Disposition": f'attachment; filename="catalog-page-{page}.csv"',
            "Cache-Control": "no-store",
        })

    @router.post("/item-catalogs", response_model=AdminDefinitionResponse, status_code=201)
    async def create_catalog(
        body: DefinitionCreateRequest, background_tasks: BackgroundTasks, response: Response,
        user_id: int = Depends(get_current_web_admin_id),
        inventory: InventoryService = Depends(inventory_dependency),
    ):
        result = await inventory.create_definition(**body.model_dump())
        response.headers["Cache-Control"] = "no-store"
        background_tasks.add_task(record_admin_action, user_id, "catalog_create", result.id)
        return AdminDefinitionResponse.from_info(result)

    @router.patch("/item-catalogs/{definition_id}", response_model=AdminDefinitionResponse)
    async def update_catalog(
        body: DefinitionUpdateRequest, background_tasks: BackgroundTasks, response: Response,
        definition_id: int = Path(ge=1),
        user_id: int = Depends(get_current_web_admin_id),
        inventory: InventoryService = Depends(inventory_dependency),
    ):
        result = await inventory.update_definition(definition_id, **body.model_dump(exclude_unset=True))
        response.headers["Cache-Control"] = "no-store"
        background_tasks.add_task(record_admin_action, user_id, "catalog_update", definition_id)
        return AdminDefinitionResponse.from_info(result)

    @router.delete("/item-catalogs/{definition_id}", status_code=204)
    async def delete_catalog(
        background_tasks: BackgroundTasks, definition_id: int = Path(ge=1),
        user_id: int = Depends(get_current_web_admin_id),
        inventory: InventoryService = Depends(inventory_dependency),
    ):
        await inventory.delete_definition(definition_id)
        background_tasks.add_task(record_admin_action, user_id, "catalog_delete", definition_id)
        return Response(status_code=204, headers={"Cache-Control": "no-store"})

    @router.get("/inventory/{item_id}/events", response_model=PageResponse[EventResponse])
    async def item_events(
        response: Response, item_id: int = Path(ge=1),
        page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
        user_id: int = Depends(get_current_web_admin_id),
        inventory: InventoryService = Depends(inventory_dependency),
    ):
        rows, total = await inventory.list_item_events(item_id, page=page, size=size)
        response.headers["Cache-Control"] = "no-store"
        return PageResponse(items=[EventResponse.from_info(row) for row in rows],
                            total=total, page=page, size=size)

    return router

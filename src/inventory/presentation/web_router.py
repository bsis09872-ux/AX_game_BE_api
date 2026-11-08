"""인벤토리 화면 라우터 (GET /inventory, Jinja2)

- 로그인 확인(현재 사용자 번호)은 main에서 넘겨 받는다 (auth의 쿠키 구조를 모른다)
- 서비스의 내 아이템 목록을 20개씩 보여 준다. 화면에는 응답 모델의 공개 값만 넘긴다
- 개인 화면이라 브라우저에 저장하지 않게 한다 (Cache-Control: no-store)
- 라우터는 서비스 호출과 화면 데이터 준비만 한다 (업무 판정, DB 갱신, commit을 하지 않는다)
- GET /inventory/{item_id}: 내 아이템 상세 화면. 없는 아이템이거나 남의 아이템이면 JSON이 아니라 '찾을 수 없습니다' 화면을 404로 보여 준다 (존재 여부를 알려 주지 않는다). 그 밖의 오류는 404 화면으로 바꾸지 않는다
- 번호 형식이 틀리면(0, 음수, 숫자 아님) 서비스를 부르지 않고 422(JSON)로 응답한다
"""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import HTMLResponse

from inventory.application.service import InventoryService
from inventory.domain.exceptions import ItemNotFoundError
from inventory.presentation.dependencies import get_inventory_service
from inventory.presentation.schemas import InventoryItemDetailResponse, InventoryItemResponse


# 한 화면에 보여주는 아이템 수
PAGE_SIZE = 20

def create_inventory_web_router(
    current_user_id: Callable[..., Awaitable[int]],
) -> APIRouter:

    # 실제 로그인 화면은 main에서 전달
    router = APIRouter()

    @router.get('/inventory', response_class=HTMLResponse)
    async def get_inventory_page(
        request: Request,
        page: int = Query(1, ge=1),
        user_id: int = Depends(current_user_id),
        service: InventoryService = Depends(get_inventory_service),
    ) -> HTMLResponse:
        items, total = await service.list_my_items(user_id, page=page, size=PAGE_SIZE)

        # 전체 쪽 수 / 아이템이 없어도 1쪽 존재
        total_pages = max(1, -(-total // PAGE_SIZE))

        response = request.app.state.templates.TemplateResponse(
            request=request,
            name='inventory/index.html',
            context={
                # 화면에는 응답 모델의 공개값만
                'items': [InventoryItemResponse.from_info(item) for item in items],
                'page': page,
                'has_previous': page > 1,
                'has_next': page < total_pages
            }
        )

        # 개인 화면을 브라우저에 저장하지 않도록 함
        response.headers['Cache-Control'] = 'no-store'
        return response

    @router.get('/inventory/{item_id}', response_class=HTMLResponse)
    async def get_inventory_item_page(
        request: Request,
        item_id: int = Path(ge=1),
        user_id: int = Depends(current_user_id),
        service: InventoryService = Depends(get_inventory_service)
    ) -> HTMLResponse:
        templates = request.app.state.templates

        try:
            info = await service.get_my_item(user_id, item_id)
        except ItemNotFoundError:

            #없는 아이템과 남의 아이템은 같은 화면 (존재여부를 알 수 없음)
            response = templates.TemplateResponse(
                request=request,
                name='inventory/not_found.html',
                context={},
                status_code=404
            )
        else:
            response = templates.TemplateResponse(
                request=request,
                name='inventory/detail.html',
                # 화면에는 응답 모델의 공개 값만 노출
                context={'item': InventoryItemDetailResponse.from_info(info)}
            )

        # 개인 화면을 브라우저에 저장하지 않게 함
        response.headers['Cache-Control'] = 'no-store'
        return response

    return router
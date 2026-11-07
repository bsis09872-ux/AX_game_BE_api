"""인벤토리 화면 라우터 (GET /inventory, Jinja2)

- 로그인 확인(현재 사용자 번호)은 main에서 넘겨 받는다 (auth의 쿠키 구조를 모른다)
- 서비스의 내 아이템 목록을 20개씩 보여 준다. 화면에는 응답 모델의 공개 값만 넘긴다
- 개인 화면이라 브라우저에 저장하지 않게 한다 (Cache-Control: no-store)
- 라우터는 서비스 호출과 화면 데이터 준비만 한다 (업무 판정, DB 갱신, commit을 하지 않는다)
"""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from inventory.application.service import InventoryService
from inventory.presentation.dependencies import get_inventory_service
from inventory.presentation.schemas import InventoryItemResponse


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

    return router
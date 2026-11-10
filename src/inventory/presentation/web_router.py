"""인벤토리 화면 라우터 (GET /inventory, Jinja2)

- 로그인 확인(현재 사용자 번호)은 main에서 넘겨 받는다 (auth의 쿠키 구조를 모른다)
- 서비스의 내 아이템 목록을 20개씩 보여 준다. 화면에는 응답 모델의 공개 값만 넘긴다
- 개인 화면이라 브라우저에 저장하지 않게 한다 (Cache-Control: no-store)
- 라우터는 서비스 호출과 화면 데이터 준비만 한다 (업무 판정, DB 갱신, commit을 하지 않는다)
- GET /inventory/{item_id}: 내 아이템 상세 화면. 없는 아이템이거나 남의 아이템이면 JSON이 아니라 '찾을 수 없습니다' 화면을 404로 보여 준다 (존재 여부를 알려 주지 않는다). 그 밖의 오류는 404 화면으로 바꾸지 않는다
- 번호 형식이 틀리면(0, 음수, 숫자 아님) 서비스를 부르지 않고 422(JSON)로 응답한다
- GET /item-catalogs: 도감(아이템 카탈로그 목록) 화면. 로그인한 사용자만 보고, 한 페이지에 모두 보여 준다(page=1, size=100). 분류·희귀도로 거를 수 있고 값이 틀리면 422다. 줄마다 id="item-{번호}"가 있어 내 아이템 상세에서 해당 줄로 바로 이동한다
- GET /inventory는 상태(status)·분류(category)·희귀도(rarity)·정렬(sort)로 거를 수 있고, 값은 서비스에 그대로 넘긴다. 값이 틀리면 서비스를 부르지 않고 422다
- 필터 링크는 나머지 필터를 유지하고 쪽은 1쪽으로 돌아간다. 기본 정렬(최근 획득순)은 주소에 넣지 않는다. 이전·다음 링크는 필터와 정렬을 유지한다
- 필터 줄과 주소를 만드는 도우미는 web_filters.py에 있다 (이 파일은 서비스 호출과 화면 데이터 연결만 한다)
"""

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import get_args

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from inventory.application.service import InventoryService
from inventory.domain.exceptions import ItemNotFoundError
from inventory.presentation.dependencies import get_inventory_service
from inventory.presentation.router import Category, Rarity, InventorySort, Status
from inventory.presentation.web_filters import DEFAULT_SORT, filter_groups, inventory_href
from inventory.presentation.schemas import (
    InventoryItemDetailResponse,
    InventoryItemResponse,
    ItemDefinitionResponse,
)


# 한 화면에 보여주는 아이템 수
PAGE_SIZE = 20

# 도감은 한 화면으로 보여준다 (지금 수준에서 페이지 만들면 꼬일 수 있음)
CATALOG_PAGE_SIZE = 100

# [Claude] 경매 등록 화면 주소: 인벤토리는 경매 코드를 import하지 않고 주소만 안다 (경매 화면 URL이 바뀌면 여기도 바꾼다)
AUCTION_NEW_URL = '/auctions/new'


# [Claude] 선택한 아이템을 경매에 올릴 수 없는 이유 (올릴 수 있으면 빈 글자)
def listing_block_reason(info, now: datetime) -> str:
    if info.status != 'OWNED':
        return '이미 경매에 올라가 있는 아이템이에요.'
    resale_at = info.resale_available_at
    if resale_at is not None:
        # 시각이 시간대 없이 저장돼 있어도 UTC로 보고 비교한다
        aware = resale_at if resale_at.tzinfo is not None else resale_at.replace(tzinfo=timezone.utc)
        if aware > now:
            return f'아직 다시 팔 수 없어요. ({aware.strftime("%Y-%m-%d %H:%M:%S")} UTC 이후)'
    return ''


def create_inventory_web_router(
    current_user_id: Callable[..., Awaitable[int]],
    wallet_reader: Callable[..., Awaitable[dict | None]] | None = None,
) -> APIRouter:
    # [Claude] wallet_reader(session, user_id): 가방의 지갑 박스(잔액, 묶인 골드, 사용 가능 골드) 또는 None. main이 넘긴다(wallet을 import하지 않는다)
    # 헤더의 사용 가능 금액은 공통 헤더(static/wallet-balance.js, 지갑 담당)가 채운다

    # 실제 로그인 화면은 main에서 전달
    router = APIRouter()

    @router.get('/inventory', response_class=HTMLResponse)
    async def get_inventory_page(
        request: Request,
        status: Status | None=None,
        category: Category | None=None,
        rarity: Rarity | None=None,
        sort: InventorySort = DEFAULT_SORT,
        page: int = Query(1, ge=1),
        item: int | None = Query(None, ge=1),
        user_id: int = Depends(current_user_id),
        service: InventoryService = Depends(get_inventory_service),
        session: AsyncSession = Depends(get_db),
    ) -> HTMLResponse:
        items, total = await service.list_my_items(user_id, status=status, category=category, rarity=rarity, sort=sort, page=page, size=PAGE_SIZE)

        # 전체 쪽 수 / 아이템이 없어도 1쪽 존재
        total_pages = max(1, -(-total // PAGE_SIZE))

        # region [Claude] 가방: 선택한 아이템, 지갑 박스, 헤더 골드
        # 선택한 아이템은 내 아이템만 보여 준다 (남의 것·없는 번호는 선택 없음으로 본다)
        selected = None
        if item is not None:
            try:
                info = await service.get_my_item(user_id, item)
            except ItemNotFoundError:
                info = None
            if info is not None:
                reason = listing_block_reason(info, datetime.now(timezone.utc))
                selected = {
                    'id': info.id,
                    'definition': ItemDefinitionResponse.from_info(info.definition),
                    'can_list': not reason,
                    'reason': reason,
                }

        wallet = await wallet_reader(session, user_id) if wallet_reader else None

        # 칸을 누르면 같은 필터·정렬·쪽에서 그 아이템이 선택된다
        keep = dict(status=status, category=category, rarity=rarity, sort=sort, page=page if page > 1 else None)
        slots = [
            {
                'item': InventoryItemResponse.from_info(info),
                'href': inventory_href(**keep, item=info.id),
                'selected': item == info.id,
                'listed': info.status == 'LISTED',
            }
            for info in items
        ]
        # endregion

        response = request.app.state.templates.TemplateResponse(
            request=request,
            name='inventory/index.html',
            context={
                # 화면에는 응답 모델의 공개값만
                'slots': slots,
                'empty_slots': max(0, PAGE_SIZE - len(items)),
                'selected': selected,
                'wallet': wallet,
                'auction_new_url': AUCTION_NEW_URL,
                'page': page,
                'total_pages': total_pages,  # [Claude] 쪽 이동에 "2 / 4 쪽"을 보여 준다
                'has_previous': page > 1,
                'has_next': page < total_pages,
                # 이전·다음 링크는 지금의 필터와 정렬 유지
                'prev_url': inventory_href(status=status, category=category, rarity=rarity, sort=sort, page=page-1),
                'next_url': inventory_href(status=status, category=category, rarity=rarity, sort=sort, page=page+1),
                'filter_groups': filter_groups(status, category, rarity, sort),
                # 필터가 있는데 결과가 없을 때와 원래 비어 있을 때의 안내
                'filtered': bool(status or category or rarity)
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
        service: InventoryService = Depends(get_inventory_service),
    ) -> HTMLResponse:
        templates = request.app.state.templates

        try:
            info = await service.get_my_item(user_id, item_id)
        except ItemNotFoundError:

            #없는 아이템과 남의 아이템은 같은 화면 (존재여부를 알 수 없음)
            response = templates.TemplateResponse(
                request=request,
                name='inventory/not_found.html',
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

    @router.get('/item-catalogs', response_class=HTMLResponse, dependencies=[Depends(current_user_id)])
    async def get_catalog_page(
        request: Request,
        category: Category | None=None,
        rarity: Rarity | None=None,
        item: int | None = Query(None, ge=1),  # [Claude] 가방에서 넘어온 선택 아이템 번호 (돌아갈 때 다시 선택하려고 링크에 실어 나른다)
        service: InventoryService = Depends(get_inventory_service),
    ) -> HTMLResponse:
        definitions, _ = await service.list_definitions(
            category=category,
            rarity=rarity,
            sort='rarity_desc',
            page=1,
            size=CATALOG_PAGE_SIZE
        )

        response = request.app.state.templates.TemplateResponse(
            request=request,
            name='inventory/catalogs.html',
            context={
                # 화면에는 응답 모델의 공개값만
                'definitions': [ItemDefinitionResponse.from_info(d) for d in definitions],
                'category': category,
                'rarity': rarity,
                'back_item': item,  # [Claude]
                # 필터 링크에 쓸 허용값
                'categories': get_args(Category),
                'rarities': get_args(Rarity),
            }
        )

        response.headers['Cache-Control'] = 'no-store'
        return response

    return router
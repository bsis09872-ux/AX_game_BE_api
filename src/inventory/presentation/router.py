"""인벤토리·카탈로그 조회 API 라우터 (/v1)

- GET /v1/inventory, GET /v1/inventory/{item_id}: 내 인벤토리 목록과 상세
- GET /v1/item-catalogs, GET /v1/item-catalogs/{definition_id}: 아이템 카탈로그 목록과 상세
- 라우터는 입력 검증, 서비스 호출, 응답 변환만 한다 (업무 판정, DB 갱신, commit을 하지 않는다)
- 소유자 ID는 요청 값이 아니라 검증된 인증 정보에서 얻는다
- 오류 응답은 팀 공통 핸들러가 만든다 (이 계층에서 예외를 HTTP 오류로 바꾸지 않는다)
"""

from typing import Literal

from fastapi import APIRouter, Depends, Path, Query

from inventory.application.contracts import CurrentUser
from inventory.application.service import InventoryService
from inventory.presentation.dependencies import get_current_user, get_inventory_service
from inventory.presentation.schemas import (
    InventoryItemDetailResponse,
    InventoryItemResponse,
    ItemDefinitionResponse,
    PageResponse,
)

router = APIRouter(tags=['inventory'])


# 쿼리에 허용되는 값 (오류 시 422)
Status = Literal['OWNED', 'LISTED']
Category = Literal['FISH', 'GEM', 'MISC']
Rarity = Literal['COMMON', 'UNCOMMON', 'RARE', 'EPIC', 'LEGENDARY']


# 내 인벤토리 조회
@router.get('/inventory', response_model=PageResponse[InventoryItemResponse])
async def list_my_items(
    status: Status | None=None,
    category: Category | None=None,
    rarity: Rarity | None=None,
    sort: Literal['acquired_desc', 'rarity_desc', 'name_asc'] = 'acquired_desc',
    page: int = Query(1, ge=1),            # 1 이상
    size: int = Query(20, ge=1, le=100),   # 1 이상 100 이하
    user: CurrentUser = Depends(get_current_user),
    service: InventoryService = Depends(get_inventory_service),
) -> PageResponse[InventoryItemResponse]:
    items, total = await service.list_my_items(
        user.id, status=status, category=category, rarity=rarity, sort=sort, page=page, size=size
    )
    return PageResponse(
        items=[InventoryItemResponse.from_info(item) for item in items],
        page=page, size=size, total=total,
    )


# 내 아이템 상세 조회
@router.get('/inventory/{item_id}', response_model=InventoryItemDetailResponse)
async def get_my_item(
    item_id: int = Path(ge=1),
    user: CurrentUser = Depends(get_current_user),
    service: InventoryService = Depends(get_inventory_service),
) -> InventoryItemDetailResponse:
    return InventoryItemDetailResponse.from_info(await service.get_my_item(user.id, item_id))


# 아이템 종류 목록 조회 / 공통 정보이긴 하지만 로그인한 사용자만 볼 수 있게 함
@router.get(
    '/item-catalogs',
    response_model=PageResponse[ItemDefinitionResponse],
    dependencies=[Depends(get_current_user)],
)
async def list_definitions(
    category: Category | None=None,
    rarity: Rarity | None=None,
    sort: Literal['rarity_desc', 'name_asc'] = 'rarity_desc',
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    service: InventoryService = Depends(get_inventory_service),
) -> PageResponse[ItemDefinitionResponse]:
    definitions, total = await service.list_definitions(
        category=category, rarity=rarity, sort=sort, page=page, size=size
    )
    return PageResponse(
        items=[ItemDefinitionResponse.from_info(definition) for definition in definitions],
        page=page, size=size, total=total,
    )


# 아이템 종류 상세 조회 / 공통 정보이긴 하지만 로그인한 사용자만 볼 수 있게 함
@router.get(
    '/item-catalogs/{definition_id}',
    response_model=ItemDefinitionResponse,
    dependencies=[Depends(get_current_user)],
)
async def get_definition(
    definition_id: int = Path(ge=1),
    service: InventoryService = Depends(get_inventory_service),
) -> ItemDefinitionResponse:
    return ItemDefinitionResponse.from_info(await service.get_definition(definition_id))

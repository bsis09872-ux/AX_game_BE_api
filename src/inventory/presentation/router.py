"""인벤토리·카탈로그 조회 API 라우터 (/v1)

- GET /v1/inventory, GET /v1/inventory/{item_id}: 내 인벤토리 목록과 상세
- GET /v1/item-catalogs, GET /v1/item-catalogs/{definition_id}: 아이템 카탈로그 목록과 상세
- 라우터는 입력 검증, 서비스 호출, 응답 변환만 한다 (업무 판정, DB 갱신, commit을 하지 않는다)
- 소유자 ID는 요청 값이 아니라 검증된 인증 정보에서 얻는다
- 오류 응답은 팀 공통 핸들러가 만든다 (이 계층에서 예외를 HTTP 오류로 바꾸지 않는다)
- GET /v1/inventory/{item_id}/events: 관리자용 아이템 이력 조회 (오래된 순, 페이지)
- GET /v1/inventory는 응답을 보낸 뒤 접근 로그 한 줄(사용자 번호, 이번에 돌려준 건수)을 백그라운드로 남긴다
  - 읽기 요청의 부가 기록만 백그라운드로 넘긴다. 상태를 바꾸는 일(저장, 지급, 예약 등)은 넘기지 않는다: 실패해도 사용자가 알 수 없고, 응답은 이미 성공으로 나간 뒤이기 때문이다
  - 토큰, 필터 값, 아이템 이름은 로그에 넣지 않는다
"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, BackgroundTasks

from shared.core.openapi import errors

from inventory.application.contracts import CurrentUser
from inventory.application.service import InventoryService
from inventory.presentation.dependencies import get_current_user, get_inventory_service, require_admin

from inventory.presentation.schemas import (
    AdminDefinitionResponse,
    DefinitionCreateRequest,
    DefinitionUpdateRequest,
    EventResponse,
    InventoryItemDetailResponse,
    InventoryItemResponse,
    ItemDefinitionResponse,
    PageResponse,
)

logger = logging.getLogger(__name__)


# 내 인벤토리를 조회한 기록 (응답을 보낸 뒤 실행)
# 읽기 요청의 sub 기록이므로 실패해도 영향도 낮음
# 토큰, 필터 값, 아이템 이름은 남지 않는다
def _log_inventory_access(user_id: int, count: int) -> None:
    logger.info('inventory_viewed user_id=%s count=%s', user_id, count)


router = APIRouter(tags=['inventory'])


# 쿼리에 허용되는 값 (오류 시 422)
Status = Literal['OWNED', 'LISTED']
Category = Literal['FISH', 'GEM', 'MISC']
Rarity = Literal['COMMON', 'UNCOMMON', 'RARE', 'EPIC', 'LEGENDARY']
InventorySort = Literal['acquired_desc', 'rarity_desc', 'name_asc']


# 내 인벤토리 조회
@router.get(
    '/inventory',
    response_model=PageResponse[InventoryItemResponse],
    summary='내 아이템 목록 조회',
    description='로그인한 사용자가 가진 아이템을 상태·분류·희귀도로 거르고 정렬해 페이지 단위로 돌려줍니다.',
    responses=errors(401),
)
async def list_my_items(

    # 기본값이 없는 매개변수는 기본값이 있는 것보다 앞에 와야 한다
    background_tasks: BackgroundTasks,
    status: Status | None=None,
    category: Category | None=None,
    rarity: Rarity | None=None,
    sort: InventorySort = 'acquired_desc',
    page: int = Query(1, ge=1),            # 1 이상
    size: int = Query(20, ge=1, le=100),   # 1 이상 100 이하
    user: CurrentUser = Depends(get_current_user),
    service: InventoryService = Depends(get_inventory_service),
) -> PageResponse[InventoryItemResponse]:
    items, total = await service.list_my_items(
        user.id, status=status, category=category, rarity=rarity, sort=sort, page=page, size=size
    )

    # 응답을 보낸 뒤에 로그가 남도록 예약 (함수 없이 이름과 인자 기록)
    background_tasks.add_task(_log_inventory_access, user.id, len(items))


    return PageResponse(
        items=[InventoryItemResponse.from_info(item) for item in items],
        page=page, size=size, total=total,
    )


# 내 아이템 상세 조회
@router.get(
    '/inventory/{item_id}',
    response_model=InventoryItemDetailResponse,
    summary='내 아이템 상세 조회',
    description='남의 아이템이나 없는 아이템은 존재 여부를 숨기려고 똑같이 404로 응답합니다.',
    responses=errors(401, 404),
)
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
    summary='아이템 카탈로그 목록 조회',
    description='서버에 등록된 아이템 종류(도감)를 분류·희귀도로 거르고 정렬해 돌려줍니다. 낚시 가중치는 보이지 않습니다.',
    responses=errors(401),
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
    summary='아이템 카탈로그 상세 조회',
    responses=errors(401, 404),
)
async def get_definition(
    definition_id: int = Path(ge=1),
    service: InventoryService = Depends(get_inventory_service),
) -> ItemDefinitionResponse:
    return ItemDefinitionResponse.from_info(await service.get_definition(definition_id))

# ===== 관리자 카탈로그 관리 (ADMIN만) =====

# 카탈로그 생성
@router.post(
    '/item-catalogs',
    status_code=201,
    response_model=AdminDefinitionResponse,
    dependencies=[Depends(require_admin)],
    summary='아이템 카탈로그 생성 (관리자)',
    description='`code`는 영문 소문자로 시작하는 3~50자이고 겹칠 수 없습니다. 시작가는 1 이상, 가중치는 0 이상입니다.',
    responses=errors(400, 401, 403),
)
async def create_definition(
    body: DefinitionCreateRequest,
    service: InventoryService = Depends(get_inventory_service)
) -> AdminDefinitionResponse:
    return AdminDefinitionResponse.from_info(await service.create_definition(**body.model_dump()))


# 카탈로그 수정
@router.patch(
    '/item-catalogs/{definition_id}',
    response_model=AdminDefinitionResponse, # 응답을 내보낼 형식
    dependencies=[Depends(require_admin)],  # 관리자 여부 확인
    summary='아이템 카탈로그 수정 (관리자)',
    description='보낸 항목만 바꿉니다. `name`과 `category`는 만든 뒤 바꿀 수 없습니다.',
    responses=errors(400, 401, 403, 404),
)
async def update_definition(
    body: DefinitionUpdateRequest,   # 요청 본문 형식 / 이상하면 422
    definition_id: int = Path(ge=1), # 요청을 위해 str → int
    service: InventoryService = Depends(get_inventory_service) # 받을 서비스
) -> AdminDefinitionResponse:
    # DTO를 응답 모양으로 바꾼다 
    return AdminDefinitionResponse.from_info(

        await service
        # 서비스가 조회 → 도메인(규칙검사) → 저장 → 커밋 흐름으로 DTO 반환 
        .update_definition(definition_id, 
                           # 요청 객체를 딕셔너리로 바꾸는데 클라이언트가 실제로 보낸 필드만 넣는다
                           **body.model_dump(exclude_unset=True))
    )


# 카탈로그 삭제
@router.delete(
    '/item-catalogs/{definition_id}',
    status_code=204,
    dependencies=[Depends(require_admin)],
    summary='아이템 카탈로그 삭제 (관리자)',
    description='이미 아이템이 만들어진 카탈로그는 지울 수 없습니다(400).',
    responses=errors(400, 401, 403, 404),
)
async def delete_definition(
    definition_id: int = Path(ge=1),
    service: InventoryService = Depends(get_inventory_service)
) -> None:
    await service.delete_definition(definition_id)


# ===== 관리자 아이템 이력 관리 (ADMIN만) =====

# 아이템 이력 조회
@router.get(
    '/inventory/{item_id}/events',
    response_model=PageResponse[EventResponse],
    dependencies=[Depends(require_admin)],
    summary='아이템 이력 조회 (관리자)',
    description='아이템의 지급·예약·해제·이전 기록을 오래된 순으로 돌려줍니다.',
    responses=errors(401, 403, 404),
)
async def list_item_events(
    item_id: int = Path(ge=1),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    service: InventoryService = Depends(get_inventory_service)
) -> PageResponse[EventResponse]:
    events, total = await service.list_item_events(item_id, page=page, size=size)
    return PageResponse(
        items=[EventResponse.from_info(event) for event in events], page=page, size=size, total=total
    )
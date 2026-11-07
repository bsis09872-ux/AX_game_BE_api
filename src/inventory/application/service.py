"""인벤토리 서비스: 조회, 지급(grant_item), 트랜잭션 조율

- 요청 하나의 순서를 맞춘다: 레포지토리로 읽기 -> 도메인 메서드로 규칙 판정 -> 저장 -> commit
- commit은 이 서비스가 맡고, 오류가 났을 때 rollback은 팀 공통 get_db가 맡는다 (레포지토리는 flush까지만 한다)
- 아이템의 속성과 소유자는 서버가 정한다. 클라이언트가 보내는 것은 어느 아이템인지 식별자뿐이다
- 아이템 생성은 grant_item만 한다 (HTTP로 아이템을 직접 만드는 경로를 만들지 않는다)
- 남의 아이템 조회는 "없음"으로 응답한다 (존재 자체를 숨긴다)
- 규칙 판정을 여기서 if-else로 하지 않는다 (도메인에 맡긴다)
- 로그는 logging.getLogger(__name__)로 남긴다 (설정은 팀 공통 shared.core.logging_config가 한다)
- 저장 성공 로그는 commit 성공 후에 남긴다
- 읽기 메서드는 commit하지 않는다. 지급(grant_item)만 저장 뒤에 commit한다
- reserve_for_listing, release_from_listing, transfer_to는 auction에게 공개하는 메서드이고 commit하지 않는다. commit과 rollback은 부른 쪽의 정산 트랜잭션이 한다
    - 이 메서드들은 아이템 행을 먼저 잠그고(잠근 뒤의 최신 상태로 판정) 규칙 위반은 도메인 예외를 그대로 올린다
- get_item은 소유자를 확인하지 않는 내부용 읽기이고(3번의 거래 기록 스냅샷용), transfer_to의 from_owner_id는 값이 오면 현재 소유자와 다를 때 NotOwnerError로 거절한다
- 카탈로그 관리(create_definition, update_definition, delete_definition)는 저장 뒤에 commit하고, 값 규칙은 도메인에 맡긴다. 서비스는 중복 code, 사용 중 삭제, 없음만 판정한다
- 오류 로그는 팀 공통 핸들러가 남기므로 여기서 중복해서 남기지 않는다. 토큰·비밀번호·요청 본문은 남기지 않는다
- FastAPI와 SQLAlchemy의 세부 사항을 모른다
"""

import logging
from datetime import datetime

from inventory.application.contracts import (
    DefinitionRepository,
    ItemRepository, 
    UnitOfWork, 
    UserLookup
)
from inventory.application.dto import DefinitionInfo, ItemInfo
from inventory.domain.enums import ItemOrigin

from inventory.domain.exceptions import (
    DefinitionNotFoundError,
    DefinitionCodeDuplicateError,
    DefinitionInUseError,
    ItemNotFoundError,
    NotOwnerError,
    OwnerNotFoundError
)
from inventory.domain.inventory_item import InventoryItem
from inventory.domain.item_definition import ItemDefinition

# 성공 로그
logger = logging.getLogger(__name__)

# 도메인 객체 → DTO
def _to_definition_info(definition: ItemDefinition) -> DefinitionInfo:
    return DefinitionInfo(
        id=definition.id,
        code=definition.code,
        name=definition.name,
        category=definition.category.value,
        rarity=definition.rarity.value,
        icon=definition.icon,
        start_price=definition.start_price,
        description=definition.description,
        weight=definition.weight,
        fishable=definition.fishable,
    )

# 도메인 객체 → DTO
def _to_item_info(item: InventoryItem) -> ItemInfo:
    return ItemInfo(
        id=item.id,
        definition=_to_definition_info(item.definition),
        owner_id=item.owner_id,
        status=item.status.value,
        origin=item.origin.value,
        acquired_at=item.acquired_at,
        resale_available_at=item.resale_available_at,
    )

# 의존성 주입
class InventoryService:

    def __init__(
        self,
        items: ItemRepository,
        definitions: DefinitionRepository,
        user_lookup: UserLookup,
        unit_of_work: UnitOfWork
    ) -> None:
        self._items = items
        self._definitions = definitions
        self._user_lookup = user_lookup
        self._unit_of_work = unit_of_work

    # 내 아이템 목록
    async def list_my_items(
            self, owner_id: int, *, status=None, category=None, rarity=None, sort: str = 'acquired_desc', page: int = 1, size: int = 20
    ) -> tuple[list[ItemInfo], int]:
        items, total = await self._items.find_by_owner(
            owner_id, status=status, category=category, rarity=rarity, sort=sort, page=page, size=size
        )
        return [_to_item_info(item) for item in items], total

    # 내 아이템 상세
    async def get_my_item(self, owner_id: int, item_id: int) -> ItemInfo:
        item = await self._items.find_by_id(item_id)
        if item is None or item.owner_id != owner_id:
            raise ItemNotFoundError()
        return _to_item_info(item)

    # 아이템 상세 (소유자 확인 없이 시스템(내부)이 읽는 용도)
    # 거래 정산 후 소유자가 구매자로 바뀌어서 get_my_item 사용이 불가하므로 필요한 함수이고 API로는 열지 않는다 (읽기만)
    async def get_item(self, item_id: int) -> ItemInfo:
        item = await self._items.find_by_id(item_id)
        if item is None:
            raise ItemNotFoundError()
        return _to_item_info(item)

    # 카탈로그 목록
    async def list_definitions(
        self, *, category=None, rarity=None, sort: str = 'rarity_desc',
        page: int = 1, size: int = 20,
    ) -> tuple[list[DefinitionInfo], int]:
        definitions, total = await self._definitions.find_all(
            category=category, rarity=rarity, sort=sort, page=page, size=size
        )
        return [_to_definition_info(definition) for definition in definitions], total

    async def get_definition(self, definition_id: int) -> DefinitionInfo:
        definition = await self._definitions.find_by_id(definition_id)
        if definition is None:
            raise DefinitionNotFoundError()
        return _to_definition_info(definition)

    # 관리자 카탈로그 관리 (commit 대상)

    # 카탈로그 생성
    # shortcut: 동시에 같은 code로 만들면 둘 다 중복 확인을 통과해 DB 유일 제약 오류(500)가 발생
    async def create_definition(
            self, *, code:str, name: str, category: str, rarity: str, start_price: int, description: str = '', icon: str = 'default', weight: int = 10, fishable: bool = True
    ) -> DefinitionInfo:
        definition = ItemDefinition(
            code=code, name=name, category=category, rarity=rarity, start_price=start_price, description=description, icon=icon, weight=weight, fishable=fishable
        )

        if await self._definitions.find_by_code(definition.code) is not None:
            raise DefinitionCodeDuplicateError()

        await self._definitions.save(definition)
        await self._unit_of_work.commit()
        logger.info('definition_created definition_id=%s', definition.id)
        return _to_definition_info(definition)

    # 카탈로그 수정
    async def update_definition(
        self, definition_id: int, *, name=None, category=None, weight=None, fishable=None, icon=None, description=None, start_price=None
    ) -> DefinitionInfo:
        definition = await self._definitions.find_by_id(definition_id)
        if definition is None:
            raise DefinitionNotFoundError()

        definition.update(
            name=name, category=category, weight=weight, fishable=fishable, icon=icon, description=description, start_price=start_price
        )
        await self._definitions.save(definition)
        await self._unit_of_work.commit()
        logger.info('definition_updated definition_id=%s', definition.id)
        return _to_definition_info(definition)

    # 카탈로그 삭제
    async def delete_definition(self, definition_id: int) -> None:
        definition = await self._definitions.find_by_id(definition_id)
        if definition is None:
            raise DefinitionNotFoundError()
        if await self._definitions.count_items(definition_id) > 0:
            raise DefinitionInUseError()

        await self._definitions.delete(definition)
        await self._unit_of_work.commit()
        logger.info('definition_deleted definition_id=%s', definition_id)

    # 아이템 지급 (저장 후 flush가 아닌 commit) 
    async def grant_item(
            self, definition_id: int, owner_id: int, origin: ItemOrigin, now:datetime, actor_id: int | None=None
    ) -> ItemInfo:

        # 1. 카탈로그가 있는지 
        definition = await self._definitions.find_by_id(definition_id)
        if definition is None:
            raise DefinitionNotFoundError()

        # 2. 활성 사용자인지
        if owner_id not in await self._user_lookup.find_active_user_ids([owner_id]):
            raise OwnerNotFoundError()

        # 3. 규칙에 따라 아이템 지급
        item = InventoryItem.grant(definition, owner_id, origin, now, actor_id=actor_id)

        # 4. 저장
        await self._items.save(item)
        await self._unit_of_work.commit()

        # 5. 성공 로그
        logger.info(
            'item_granted item_id=%s definition_id=%s owner_id=%s origin=%s',
            item.id, definition.id, owner_id, origin.value
        )
        return _to_item_info(item)

    # ===== 옥션 도메인에게 공개하는 메서드 =====
    # commit하지 않는다. commit과 rollback은 부른 쪽(3번의 정산 트랜잭션)이 한다
    # 그래서 정산이 실패해 rollback하면 아이템 변경과 이력이 함께 원래대로 돌아간다
    # 성공 로그도 남기지 않는다 (저장 성공 로그는 commit 뒤에 남기는 규칙인데 여기서는 commit하지 않으므로)

    # 아이템 행을 잠그고 가져온다. 없으면 없음
    # 잠금 덕분에 같은 아이템에 동시에 요청이 와도 한 번에 하나씩만 처리된다
    async def _lock(self, item_id: int) -> InventoryItem:
        item = await self._items.find_by_id_for_update(item_id)
        if item is None:
            raise ItemNotFoundError()
        return item

    # 판매 예약 (OWNED -> LISTED)
    # 소유자인지, 상태가 맞는지, 재판매 제한이 지났는지는 도메인 메서드가 판정한다
    # 위반하면 도메인 예외(NotOwnerError, InvalidStateError, ResaleNotAvailableError)가 그대로 올라온다
    async def reserve_for_listing(
        self, item_id: int, by_owner_id: int, now: datetime, listing_id: int | None=None
    ) -> ItemInfo:
        item = await self._lock(item_id)
        item.reserve_for_listing(by_owner_id, now, listing_id=listing_id)
        # 아이템과 쌓인 이력(LISTED)을 같이 저장한다 (flush만)
        await self._items.save(item)
        return _to_item_info(item)

    # 판매 예약 해제 (Listed -> OWNED, 판매자 그대로) : 유찰, 취소 등
    async def release_from_listing(
        self, item_id: int, by_owner_id: int, now: datetime, listing_id: int | None=None
    ) -> ItemInfo:
        item = await self._lock(item_id)
        item.release_from_listing(by_owner_id, now, listing_id=listing_id)
        await self._items.save(item)
        return _to_item_info(item)

    # 소유권 이전 (LISTED -> OWNED, 낙찰자) : 지급 출처 = TRADE, 재판매 제한 적용
    async def transfer_to(
        self, item_id: int, new_owner_id: int, now: datetime, listing_id: int | None=None, trade_id: int | None=None,
        from_owner_id: int | None=None,
    ) -> ItemInfo:
        item = await self._lock(item_id)

        # 현재 소유자(판매자)가 맞는지 확인
        # 판매자가 아닌 사람의 아이템을 잘못 넘기는 것을 방지
        if from_owner_id is not None and item.owner_id != from_owner_id:
            raise NotOwnerError()

        if new_owner_id not in await self._user_lookup.find_active_user_ids([new_owner_id]):
            raise OwnerNotFoundError()
        item.transfer_to(new_owner_id, now, listing_id=listing_id, trade_id=trade_id)
        await self._items.save(item)
        return _to_item_info(item)

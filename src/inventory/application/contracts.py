"""인벤토리가 다른 도메인에 요청하는 기능의 계약 (내가 필요한 것)

- 계약은 필요한 기능의 모양(Protocol)만 적는다. 구현은 어댑터가 하고 wiring이 연결한다
- UserLookup: 주어진 사용자 번호 중 실제로 있고 탈퇴하지 않은(활성) 번호만 돌려준다
- ItemRepository, DefinitionRepository, UnitOfWork: 서비스가 저장소와 commit에게 요구하는 모양이다 (테스트에서는 가짜를 끼운다)
- 다른 도메인의 모델이나 infrastructure를 import하지 않는다
"""

from collections.abc import Iterable
from typing import Protocol

from inventory.domain.inventory_item import InventoryItem
from inventory.domain.item_definition import ItemDefinition

# 쓰는 쪽은 이 모양만 알고 누가 어떻게 구현했는지는 모른다
class UserLookup(Protocol):
    # user_ids 중 활성인 번호만 set으로 돌려준다 (없거나 탈퇴한 번호는 제외)
    async def find_active_user_ids(self, user_ids: Iterable[int]) -> set[int]:
        ...


# 서비스가 저장소에 요청하는 모양
class ItemRepository(Protocol):
    
    async def find_by_id(self, item_id: int) -> InventoryItem | None:
        ...

    # 키워드 전용 인자: 이름을 붙여서 넣고 싶을 때
    async def find_by_owner(
            self, owner_id: int, *, status=None, category=None, rarity=None,
            sort: str = 'acquired_desc', page: int = 1, size = 20,
    ) -> tuple[list[InventoryItem], int]:
        ...

    async def save(self, item: InventoryItem) -> InventoryItem:
        ...


# 서비스가 저장소에 요청하는 모양
class DefinitionRepository(Protocol):
    async def find_by_id(self, definition_id: int) -> ItemDefinition | None:
        ...

    async def find_all(
            self, *, category=None, rarity=None, sort: str = 'rarity_desc',
            page: int = 1, size: int = 20
    ) -> tuple[list[ItemDefinition], int]:
        ...


# 서비스가 확정 요청하는 모양 (커밋 부탁)
class UnitOfWork(Protocol):
    async def commit(self) -> None:
        ...
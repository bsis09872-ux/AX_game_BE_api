"""인벤토리 서비스가 밖(API, 다른 도메인)에 제공하는 데이터의 모양

- 도메인 객체(InventoryItem, ItemDefinition)를 그대로 내보내지 않고 이 모양으로 바꿔서 준다
- 값은 Enum이 아니라 글자 그대로다 (category, rarity, status, origin)
- 만든 뒤 바꾸지 않는다 (frozen)
- 어떤 필드를 사용자에게 보여 줄지는 presentation이 정한다 (weight, fishable은 관리자에게만)
"""

from dataclasses import dataclass
from datetime import datetime

# 아이템 카탈로그 정보
@dataclass(frozen=True)
class DefinitionInfo:
    id: int
    code: str
    name: str
    category: str # 'FISH', 'MISC", ...
    rarity: str
    icon: str
    start_price: int
    description: str
    weight: int
    fishable: bool

# 데코레이션이 없다면?
# class DefinitionInfo:
#     # 1. 생성자: 값을 받아 저장한다 (@dataclass가 자동으로 만들어 주는 것)
#     def __init__(self, id: int, name: str, start_price: int) -> None:
#         # frozen이라서 self.id = id 처럼 직접 대입하면 안 된다 (아래 __setattr__이 막는다)
#         # 그래서 object의 대입 방법을 써서 값을 넣는다
#         object.__setattr__(self, 'id', id)
#         object.__setattr__(self, 'name', name)
#         object.__setattr__(self, 'start_price', start_price)

#     # 2. frozen: 만든 뒤 값을 바꾸려 하면 오류를 낸다
#     def __setattr__(self, key, value):
#         raise AttributeError(f'{key}는 바꿀 수 없다 (frozen)')

#     def __delattr__(self, key):
#         raise AttributeError(f'{key}는 지울 수 없다 (frozen)')

#     # 3. 출력 모양: print(info) 했을 때 보이는 글자
#     def __repr__(self) -> str:
#         return f'DefinitionInfo(id={self.id!r}, name={self.name!r}, start_price={self.start_price!r})'

#     # 4. 같은 값이면 같다고 본다 (==)
#     def __eq__(self, other) -> bool:
#         if other.__class__ is not self.__class__:
#             return NotImplemented
#         return (self.id, self.name, self.start_price) == (other.id, other.name, other.start_price)

#     # 5. 딕셔너리 키나 set에 넣을 수 있게 한다 (frozen이면 같이 만들어 준다)
#     def __hash__(self) -> int:
#         return hash((self.id, self.name, self.start_price))

# 개별 아이템 정보
@dataclass(frozen=True)
class ItemInfo:
    id: int
    definition: DefinitionInfo
    owner_id: int
    status: str # 'OWNED' 또는 'LISTED'
    origin: str # 'SEED', 'ADMIN_GRANT', 'REWARD', 'TRADE'
    acquired_at: datetime
    resale_available_at: datetime | None 

# 아이템 이력 한 줄 (관리자 이력 조회에서 내보냄)
@dataclass(frozen=True)
class EventInfo:
    item_id: int
    event_type: str  # 'GRANTED', 'LISTED', 'UNLISTED', 'TRANSFERRED'
    from_owner_id: int | None
    to_owner_id: int | None
    actor_id: int | None
    listing_id: int | None
    trade_id: int | None
    created_at: datetime
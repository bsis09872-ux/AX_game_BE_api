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
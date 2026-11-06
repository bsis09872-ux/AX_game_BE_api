"""아이템 이력(ItemEvent): 소유나 상태가 바뀔 때마다 한 줄씩 쌓이는 기록

- 종류는 GRANTED, LISTED, UNLISTED, TRANSFERRED 네 가지다
- 값 객체다. 만든 뒤 바꾸지 않고, 수정이나 삭제하는 코드를 만들지 않는다 (쌓기만 한다)
- listing_id, trade_id는 이력에 적을 값일 뿐이다. 매물과 거래를 가리키기만 하고 FK를 걸지 않는다
- 만드는 곳은 InventoryItem이고, 저장은 아이템과 같은 트랜잭션으로 레포지토리가 한다
- 순수 파이썬만 쓴다 (FastAPI, Pydantic, SQLAlchemy, logging을 import하지 않는다)
"""

from dataclasses import dataclass
from datetime import datetime

from inventory.domain.enums import ItemEventType

# frozen=True → r
@dataclass(frozen=True)
class ItemEvent:
    event_type: ItemEventType
    from_owner_id: int | None
    to_owner_id: int | None
    created_at: datetime
    actor_id: int | None=None
    listing_id: int | None=None
    trade_id: int | None=None
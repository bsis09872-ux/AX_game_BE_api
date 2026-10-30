"""ItemEvent: 아이템의 소유·상태가 바뀐 기록 1건, 순수 값 객체 (U3).

TODO(U3)
- Enum: ItemEventType(GRANTED/LISTED/UNLISTED/TRANSFERRED)
- 필드: event_type, item_id, from_owner_id, to_owner_id, actor_id, listing_id, trade_id, created_at (바꿀 수 없는 객체)
- 만드는 곳: InventoryItem의 메서드(grant/reserve/release/transfer). InventoryItem이 들고 있다가 pop_events()로 내준다
- 저장하는 곳: repository.save(item)이 아이템과 같은 트랜잭션으로 저장 (item_events 테이블)
- 쌓기만 한다: 수정·삭제 메서드를 만들지 않는다
- 설계: inventory-domain 7장 (사건별로 채우는 값 표)

순수 파이썬만 사용한다. fastapi / sqlalchemy / pydantic import 금지.
"""

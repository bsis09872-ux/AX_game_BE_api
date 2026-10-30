"""InventoryItem: 계정이 소유한 고유 아이템 1개, 낱개 (U3).

TODO(U3)
- Enum: ItemStatus(OWNED/LISTED), ItemOrigin(SEED/ADMIN_GRANT/REWARD/TRADE)
- grant(definition, owner_id, origin, now, actor_id=None): 생성 팩토리(서버 내부 전용). OWNED, acquired_at=now, resale_available_at=None, GRANTED 이력
- reserve_for_listing(by_owner_id, now, listing_id=None): OWNED -> LISTED. 소유자·상태·resale_available_at 검사, LISTED 이력
- release_from_listing(by_owner_id, now, listing_id=None): LISTED -> OWNED(판매자 그대로, acquired_at 유지), UNLISTED 이력
- transfer_to(new_owner_id, now, listing_id=None, trade_id=None, resale_delay): LISTED -> OWNED(낙찰자).
  acquired_at=now, origin=TRADE, resale_available_at=now+30분, TRANSFERRED 이력
- pop_events(): 쌓인 ItemEvent를 꺼내 비운다 (repository.save가 부른다)
- 소유권이 바뀌는 경로는 transfer_to 하나뿐. 시계는 직접 읽지 않고 now 인자로 받는다
- 설계: inventory-domain 3~5장·7장, flows.md (상태 전이·이력)

순수 파이썬만 사용한다. fastapi / sqlalchemy / pydantic import 금지.
"""

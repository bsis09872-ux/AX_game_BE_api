"""Pydantic 입출력 스키마 (U8, U12).

TODO(U8)
- 응답: ItemDefinitionResponse / InventoryItemResponse(definition 포함) / 페이지 응답 (from_attributes)
- 쿼리 모델: status / category / rarity / sort / page / size
- 요청(운영자 생성·수정, U10)은 extra="forbid" — 아이템 속성을 클라이언트에서 받지 않는다
TODO(U12, 선택 S)
- ItemEventResponse: id, item_id, event_type, from_owner_id, to_owner_id, actor_id, listing_id, trade_id, created_at
- 설계: API 명세(api-spec)
"""

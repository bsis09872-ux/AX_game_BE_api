"""응용 서비스: 흐름 조율과 트랜잭션 (U7, U10, U12).

TODO(U7)
- InventoryQueryService: list_my_items / get_my_item / list_definitions / get_definition
- InventoryGrantService.grant_item(definition_id, owner_id, origin, now, actor_id=None): 서버 내부 전용 (HTTP 노출 없음)
  흐름: 종류 조회 -> InventoryItem.grant(이력 포함) -> repository.save -> commit
TODO(U10, 선택 S)
- DefinitionAdminService: create / update / delete (아이템이 있으면 DefinitionInUseError)
TODO(U12, 선택 S)
- ItemEventQueryService.list_events(item_id, page): 운영자 이력 조회(오래된 순)
- 이력은 도메인이 만들고 repository.save가 저장하므로 서비스가 이력을 직접 만들지 않는다
- 규칙 if-else는 도메인에 위임. presentation import 금지
"""

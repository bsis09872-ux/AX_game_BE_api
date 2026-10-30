"""레포지토리: ORM 모델 <-> 순수 도메인 객체 변환 (U5).

TODO(U5)
- ItemDefinitionRepository: find_by_id / find_by_code / find_all(filters, page) / save / delete / count_items
- InventoryItemRepository: find_by_id / find_by_id_for_update / find_by_owner(owner_id, filters, page) / save / find_events(item_id, page)
- save(item): 아이템을 저장하고 item.pop_events()로 꺼낸 이력을 item_events에 같이 flush (새 아이템은 id가 생긴 뒤 이력 저장)
- 이력은 추가·조회만 있다. 수정·삭제 메서드를 만들지 않는다
- find_by_id_for_update는 select(...).with_for_update()
- 희귀도 정렬은 문자열이 아니라 순위(CASE)로
- 반환은 도메인 객체만. save는 flush까지만, commit 금지 (commit은 application service)
"""

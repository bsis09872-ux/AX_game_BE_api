"""시드 데이터 주입 (U6).

TODO(U6)
- seed_inventory(session): 종류 13개 + 시연 아이템 24개(사용자 1~3, 모두 OWNED, origin=SEED) + GRANTED 이력 24건
- 재시작해도 중복 없음: 종류는 code 존재 여부, 아이템은 소유자별로 비어 있을 때만
- ItemDefinition / InventoryItem.grant를 거쳐 규칙을 통과시킨다 (직접 INSERT 금지). 이력은 repository.save가 같이 저장
- DEMO_USER_IDS는 임시값. 1번 사용자 테이블 확정 시 교체
- 설계: 시드 아이템 목록(seed-items)
"""

"""SQLAlchemy 테이블 모델 (U5).

TODO(U5)
- ItemDefinitionModel / InventoryItemModel / ItemEventModel
- DDL(db-schema)과 1:1: CHECK, FK(RESTRICT), UNIQUE(code), 인덱스(owner_id, status, acquired_at), (item_id, created_at)
- item_events: listing_id·trade_id는 FK를 걸지 않는다. 사건별 소유자 조합 CHECK(ck_item_events_owners)
- Base는 공용 database.py의 것을 사용 (공유 파일이라 변경안만 제시)
- 이 모델은 infrastructure 밖으로 나가지 않는다 (repositories.py가 도메인 객체로 변환)
"""

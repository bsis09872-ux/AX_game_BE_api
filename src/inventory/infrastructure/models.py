"""SQLAlchemy 모델: item_definitions, inventory_items, item_events 테이블

- 테이블 이름은 복수 snake_case, 컬럼은 snake_case, 기본키는 id다
- 잘못된 값이 DB에 들어가지 못하게 제약(CHECK, FK, UNIQUE)을 둔다
  category, rarity, status, origin의 허용값, start_price 0 초과, weight 0 이상, code 고유
- item_events는 쌓기만 한다. (item_id, created_at) 인덱스를 두고 listing_id, trade_id에는 FK를 걸지 않는다
- 시각 컬럼은 시간대가 있는 UTC 값이다
- 도메인 객체와 이 모델 사이의 변환은 repositories.py가 맡는다
"""

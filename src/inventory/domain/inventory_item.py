"""개별 아이템(InventoryItem): 특정 계정이 가진 아이템 한 개와 상태 전이

- 소유자는 항상 정확히 1명이고, 존재하는 아이템 카탈로그 하나를 가리킨다
- 상태는 OWNED(보관)와 LISTED(경매 판매 예약) 두 가지다
- OWNED -> LISTED: 소유자 본인만, 상태가 OWNED이고 resale_available_at이 없거나 지난 뒤에만
- LISTED -> OWNED(판매자 그대로): 소유자 본인만, acquired_at은 바꾸지 않는다
- LISTED -> OWNED(낙찰자): 새 소유자는 현재 소유자와 달라야 하고 acquired_at, origin(TRADE), resale_available_at을 갱신한다
- 소유자가 바뀌는 경로는 transfer_to 하나뿐이다. grant는 아이템을 새로 만드는 것이다
- 상태나 소유자가 바뀔 때마다 ItemEvent 1건을 만들어 들고 있고, 저장은 레포지토리가 한다
- 시각은 now를 인자로 받는다 (시계를 직접 읽지 않는다. 시간대가 있는 UTC 값이다)
- 규칙 위반은 도메인이 직접 예외를 던진다 (서비스나 라우터의 if-else로 판정하지 않는다)
- 순수 파이썬만 쓴다 (FastAPI, Pydantic, SQLAlchemy, logging을 import하지 않는다)
"""

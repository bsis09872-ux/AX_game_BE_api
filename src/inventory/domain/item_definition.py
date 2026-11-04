"""아이템 카탈로그(ItemDefinition): 서버 카탈로그에 있는 아이템의 공통 정보

- 누구의 소유물도 아니다. 사용자가 가진 개별 아이템(InventoryItem)과 구분한다
- code는 고유하고 ^[a-z][a-z0-9_]{2,49}$ 형식, name은 공백 제외 1~100자다
- category는 FISH/GEM/MISC, rarity는 COMMON~LEGENDARY만 허용한다
- start_price는 0보다 큰 정수, weight는 0 이상의 정수, icon은 1~50자다
- name과 category는 만든 뒤 바꿀 수 없다 (바꾸려 하면 도메인이 거절한다)
- start_price가 바뀌어도 이미 등록된 매물에는 영향이 없다 (매물이 등록 때 복사해 간다)
- 순수 파이썬만 쓴다 (FastAPI, Pydantic, SQLAlchemy, logging을 import하지 않는다)
"""

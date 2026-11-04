"""아이템 분류값(Enum)

- ItemCategory: FISH, GEM, MISC
- ItemRarity: COMMON, UNCOMMON, RARE, EPIC, LEGENDARY
- ItemStatus: OWNED(보관), LISTED(경매 판매 예약)
- ItemOrigin: SEED, ADMIN_GRANT, REWARD, TRADE (현재 소유자가 얻은 경로)
- ItemEventType: GRANTED, LISTED, UNLISTED, TRANSFERRED
- 멤버 이름과 밖으로 나가는 값은 같은 대문자 문자열이다 (DB 제약의 허용값과 같다)
- 순수 파이썬만 쓴다 (FastAPI, Pydantic, SQLAlchemy, logging을 import하지 않는다)
"""
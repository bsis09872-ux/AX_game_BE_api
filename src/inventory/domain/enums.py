"""아이템 분류값(Enum)

- ItemCategory: FISH, GEM, MISC
- ItemRarity: COMMON, UNCOMMON, RARE, EPIC, LEGENDARY
- ItemStatus: OWNED(보관), LISTED(경매 판매 예약)
- ItemOrigin: SEED, ADMIN_GRANT, REWARD, TRADE (현재 소유자가 얻은 경로)
- ItemEventType: GRANTED, LISTED, UNLISTED, TRANSFERRED
- 멤버 이름과 밖으로 나가는 값은 같은 대문자 문자열이다 (DB 제약의 허용값과 같다)
- 순수 파이썬만 쓴다 (FastAPI, Pydantic, SQLAlchemy, logging을 import하지 않는다)
"""

from enum import StrEnum

# 아이템 카테고리
class ItemCategory(StrEnum):
    FISH = 'FISH'
    GEM = 'GEM'
    MISC = 'MISC'

# 아이템 희귀도
class ItemRarity(StrEnum):
    COMMON = 'COMMON'
    UNCOMMON = 'UNCOMMON'
    RARE = 'RARE'
    EPIC = 'EPIC'
    LEGENDARY = 'LEGENDARY'

# 개별 아이템 상태
class ItemStatus(StrEnum):
    OWNED = 'OWNED' # 보관
    LISTED = 'LISTED' # 판매 예약 (잠금)

# 아이템 획득 경로
class ItemOrigin(StrEnum):
    SEED = 'SEED'
    ADMIN_GRANT = 'ADMIN_GRANT'
    REWARD = 'REWARD'
    TRADE = 'TRADE'

# 아이템 이력 구분
class ItemEventType(StrEnum):
    GRANTED = 'GRANTED'
    LISTED = 'LISTED' # 판매 대기열 진입
    UNLISTED = 'UNLISTED' # 유찰·취소
    TRANSFERRED = 'TRANSFERRED' # 낙찰로 소유자 변경
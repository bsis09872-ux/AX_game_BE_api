# DTO: 다른 도메인과 주고받을 데이터를 담는 변경 불가능한 객체다.
# AuctionUserState는 사용자 제한 상태, ItemSummary는 아이템 정보를 전달한다.
# 제한 계산과 DB 조회·저장은 DTO에서 수행하지 않는다.
# blocked_until은 만료돼도 이전 집계 주기의 기준이므로 그대로 전달한다.
# 시각은 timezone-aware UTC로 전달한다.
#
# [TO DO] 다음 PR의 Adapter에서 외부 데이터를 아래 필드로 변환한다.
# User: id → user_id, auction_purchase_count → purchase_count,
#       auction_blocked_until → blocked_until.
# ItemInfo: id → inventory_item_id, definition.id → item_definition_id,
#           definition.name → name, definition.start_price → start_price.

from dataclasses import dataclass
from datetime import datetime

# 사용자 영역에서 경매에 전달하는 제한 상태다.
# 사용자 ID·낙찰 횟수·제한 종료 시각을 받아 조회 시점의 값으로 보관한다.
# 횟수 계산과 제한 판단은 이 DTO가 아닌 경매 정책에서 수행한다.
@dataclass(frozen=True)
class AuctionUserState:
    user_id: int
    purchase_count: int
    blocked_until: datetime | None

# 인벤토리에서 받은 아이템 정보를 경매에 전달한다.
# 종류·시작가는 매물 생성에, 이름은 거래 기록에 사용한다.
@dataclass(frozen=True)
class ItemSummary:
    inventory_item_id: int
    item_definition_id: int
    name: str
    start_price: int
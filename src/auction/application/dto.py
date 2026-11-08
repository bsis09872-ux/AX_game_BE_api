# DTO: 계약으로 주고받을 데이터의 모양을 순수 Python 객체로 정의한다.
# ORM 객체나 HTTP 요청·응답 스키마를 이 파일에 넣지 않는다.
# [TO DO] AuctionUserState(user_id: int, purchase_count: int, blocked_until: datetime | None)
#         용도: 정산·제한 계산용 사용자 상태. contract.py의 AuctionUserGateway가 반환한다.
#         blocked_until은 만료돼도 None으로 지우지 않고 그대로 전달한다(집계 기준).
# [TO DO] ItemSummary(inventory_item_id: int, item_definition_id: int, name: str)
#         용도: 거래 기록 스냅샷용 아이템 정보. contract.py의 InventoryGateway.get_summary가 반환한다.
# 사용자 표시 이름은 DTO 없이 contract.py의 get_display_names -> dict[int, str]로 받는다.
# 제한 상태 결과는 domain의 AuctionLimitState를 재사용하고 같은 필드를 중복 정의하지 않는다.
# [TO DO] 서비스 반환값이 엔티티로 충분하면 별도 DTO를 추가하지 않는다.

# [TO DO] AuctionUserState는 frozen dataclass로 정의하고 조회 시점의 값을 전달한다.
# Adapter 변환: User.id → user_id, auction_purchase_count → purchase_count, auction_blocked_until → blocked_until.
# TradeService는 get_state로 이 DTO를 받은 뒤 정책에 Trade 시각 목록과 blocked_until을 전달한다.

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

# 인벤토리 영역에서 경매에 전달하는 아이템 정보다.
# 아이템 ID·종류 ID·이름을 받아 거래 기록 생성에 필요한 값으로 보관한다.
@dataclass(frozen=True)
class ItemSummary:
    inventory_item_id: int
    item_definition_id: int
    name: str
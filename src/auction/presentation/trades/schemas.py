# 거래 내역과 경매 참여 제한 상태의 응답 형태를 정의한다.
# [TO DO] 거래 ID·매물 ID·체결 당시 이름·낙찰가·체결 시각을 스냅샷에서 반환한다.
# [TO DO] 현재 유효 횟수·최대 횟수(3)·제한 여부·blocked_until·남은 초를 정의한다.
# [TO DO] 남은 시간은 정책이 계산한 max(blocked_until - now, 0)을 초로 표현한다.
# [TO DO] 초의 소수점 처리와 응답 필드 이름은 팀과 합의한다.
# 만료된 blocked_until이 있어도 제한 중이라는 뜻은 아니다. 제한 여부를 별도로 반환한다.
# 시간은 UTC ISO 8601로 반환하며 화면의 KST 변환은 이 스키마에서 하지 않는다.

import math
from datetime import datetime

from pydantic import BaseModel

from auction.domain.trades.entities import Trade
from auction.domain.trades.policies import AuctionLimitState


# 거래 응답: 체결 당시 스냅샷 값만 내보낸다.
class TradeResponse(BaseModel):
    id: int
    listing_id: int
    item_name: str
    seller_name: str
    buyer_name: str
    price: int
    completed_at: datetime

    @classmethod
    def from_trade(cls, trade: Trade) -> "TradeResponse":
        return cls(
            id=trade.id,
            listing_id=trade.listing_id,
            item_name=trade.item_name_snapshot,
            seller_name=trade.seller_name_snapshot,
            buyer_name=trade.buyer_name_snapshot,
            price=trade.price_snapshot,
            completed_at=trade.completed_at,
        )


class TradePageResponse(BaseModel):
    items: list[TradeResponse]
    page: int


# 입찰 제한 상태 응답. 남은 초는 올림해 제한 중인데 0초로 보이지 않게 한다.
class BidLimitResponse(BaseModel):
    purchase_count: int
    max_count: int
    is_blocked: bool
    blocked_until: datetime | None
    remaining_seconds: int

    @classmethod
    def from_state(cls, state: AuctionLimitState) -> "BidLimitResponse":
        return cls(
            purchase_count=state.purchase_count,
            max_count=state.max_count,
            is_blocked=state.is_blocked,
            blocked_until=state.blocked_until,
            remaining_seconds=math.ceil(state.remaining.total_seconds()),
        )

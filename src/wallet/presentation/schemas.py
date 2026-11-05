"""지갑·거래 응답 모델 (WALL-01, 04, 05)

- ID는 shared의 IdStr로 선언한다. DB·도메인에서는 int, JSON으로 나갈 때만 문자열.
- 금액은 int 그대로 내보낸다.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from shared.core.schemas import IdStr  # TODO: 공통 모듈 최종 위치에 맞추기

TradeRole = Literal["buy", "sell"]


class WalletResponse(BaseModel):
    """WALL-01 내 지갑 조회"""
    user_id: IdStr
    balance: int            # 총잔액 (예약금 포함)
    held_amount: int        # 내가 최고 입찰자인 BIDDING 매물의 입찰액 합계
    available_balance: int  # balance - held_amount
    updated_at: datetime    # balance가 마지막으로 바뀐 시각 (입찰·예약 변동은 반영 안 됨)


class TradeListItem(BaseModel):
    """WALL-04 내 거래 내역의 한 행"""
    trade_id: IdStr
    role: TradeRole
    listing_id: IdStr
    item_name: str
    counterpart_name: str
    price: int
    completed_at: datetime


class TradeDetailResponse(BaseModel):
    """WALL-05 거래 상세"""
    trade_id: IdStr
    listing_id: IdStr
    item_name: str
    seller_name: str
    buyer_name: str
    price: int
    completed_at: datetime
    my_role: TradeRole
    my_balance_change: int  # 구매 -price, 판매 +price

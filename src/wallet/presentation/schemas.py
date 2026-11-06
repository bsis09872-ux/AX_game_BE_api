"""지갑·거래 요청·응답 모델 (WALL-00, 01, 04, 05)

- ID는 IdStr로 선언한다. DB·도메인에서는 int, JSON으로 나갈 때만 10진 문자열.
- 금액은 int 그대로 내보낸다.
- IdStr·PageParams·PageResponse는 여러 도메인이 쓸 수 있지만, 공통 위치가 정해질 때까지
  wallet 안에 둔다. (shared/core에는 schemas.py를 두지 않는다는 현재 README 방침)
"""
from datetime import datetime
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

# 내부 int, JSON 응답에서만 "123" (JS Number는 2^53 이상 정수를 정확히 표현하지 못함)
IdStr = Annotated[int, PlainSerializer(lambda v: str(v), return_type=str, when_used="json")]

TradeRole = Literal["buy", "sell"]
T = TypeVar("T")


class PageParams(BaseModel):
    """쿼리 ?page=1&size=20 (WALL-00: page 기본 1, size 기본 20·최대 50)"""
    page: int = Field(1, ge=1, description="페이지 번호 (1부터)")
    size: int = Field(20, ge=1, le=50, description="페이지당 개수 (최대 50)")


class PageResponse(BaseModel, Generic[T]):
    items: list[T]
    page: int
    size: int
    total: int


class _FromAttrs(BaseModel):
    # application 계층의 dataclass 결과를 그대로 받아 변환한다
    model_config = ConfigDict(from_attributes=True)


class WalletResponse(_FromAttrs):
    """WALL-01 내 지갑 조회. application의 WalletView를 model_validate로 받는다."""
    user_id: IdStr
    balance: int            # 총잔액 (예약금 포함)
    held_amount: int        # 입찰로 묶인 금액 합계
    available_balance: int  # 사용 가능 금액 = balance - held_amount
    updated_at: datetime    # balance가 마지막으로 바뀐 시각


class ChargeRequest(BaseModel):
    """관리자 지갑 충전"""
    amount: int = Field(..., gt=0, description="충전 금액 (1 이상)")


class TradeListItem(_FromAttrs):
    """WALL-04 내 거래 내역의 한 행"""
    trade_id: IdStr
    role: TradeRole
    listing_id: IdStr
    item_name: str
    counterpart_name: str
    price: int
    completed_at: datetime


class TradeDetailResponse(_FromAttrs):
    """WALL-05 거래 상세"""
    trade_id: IdStr
    listing_id: IdStr
    item_name: str
    seller_name: str
    buyer_name: str
    price: int
    completed_at: datetime
    my_role: TradeRole
    my_balance_change: int  # 구매 -price, 판매 +(price - 수수료)

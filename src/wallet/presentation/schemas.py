"""지갑 요청·응답 모델 (WALL-01, 관리자 충전)

- ID는 IdStr로 선언한다. DB·도메인에서는 int, JSON으로 나갈 때만 10진 문자열.
- 금액은 int 그대로 내보낸다.
- 거래 조회(WALL-04, 05) 모델은 거래를 경매가 맡기로 해서 두지 않는다.
"""
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

# 내부 int, JSON 응답에서만 "123" (JS Number는 2^53 이상 정수를 정확히 표현하지 못함)
IdStr = Annotated[int, PlainSerializer(lambda v: str(v), return_type=str, when_used="json")]


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


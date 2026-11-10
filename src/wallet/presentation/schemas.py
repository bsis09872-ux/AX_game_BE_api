"""지갑 요청·응답 모델 (WALL-01 관리자 충전, WALL-02 내 지갑 조회)

- ID는 IdStr로 선언한다. DB·도메인에서는 int, JSON으로 나갈 때만 10진 문자열.
- 금액은 int 그대로 내보낸다.
- 거래 조회(WALL-04, 05) 모델은 거래를 경매가 맡기로 해서 두지 않는다.
"""
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

# 입력 상한: ID·금액 컬럼이 BIGINT라 넘는 값이 DB까지 가면 500이 난다. 입력 단계에서 422로 거절한다.
# (경매 auction/presentation/params.py와 같은 기준. 도메인끼리 import하지 않으려고 따로 둔다)
BIGINT_MAX = 9223372036854775807

# 내부 int, JSON 응답에서만 "123" (JS Number는 2^53 이상 정수를 정확히 표현하지 못함)
IdStr = Annotated[int, PlainSerializer(lambda v: str(v), return_type=str, when_used="json")]


class _FromAttrs(BaseModel):
    # application 계층의 dataclass 결과를 그대로 받아 변환한다
    model_config = ConfigDict(from_attributes=True)


class WalletResponse(_FromAttrs):
    """WALL-02 내 지갑 조회 (WALL-01 충전 응답도 같은 모양). application의 WalletView를 model_validate로 받는다."""
    user_id: IdStr
    balance: int            # 총잔액 (예약금 포함)
    held_amount: int        # 입찰로 묶인 금액 합계
    available_balance: int  # 사용 가능 금액 = balance - held_amount
    updated_at: datetime    # balance가 마지막으로 바뀐 시각


class WalletBalanceResponse(_FromAttrs):
    """헤더 표시용 사용 가능 금액 (웹 화면 GET /wallet/balance). 다른 값은 내보내지 않는다."""
    available_balance: int


class ChargeRequest(BaseModel):
    """WALL-01 관리자 지갑 충전"""
    amount: int = Field(..., gt=0, le=BIGINT_MAX, description="충전 금액 (1 이상, BIGINT 이하)")


"""잔액 변경 기록 (도메인 값 객체)

Wallet이 잔액을 바꿀 때마다 "무엇이 얼마나 바뀌었는지"를 한 덩어리로 표현한다.
어디에 어떻게 남길지(서버 로그 등)는 도메인이 모르고 infrastructure가 정한다.
"""
from dataclasses import dataclass

from wallet.domain.service import BalanceEventType


@dataclass(frozen=True)
class BalanceChange:
    """트랜잭션 안에서 만들어지고, 호출자의 commit이 성공한 뒤에 기록된다."""
    event_type: BalanceEventType
    user_id: int
    balance_before: int
    amount: int  # 증가는 양수, 감소는 음수
    listing_id: int | None = None
    trade_id: int | None = None

    @property
    def balance_after(self) -> int:
        return self.balance_before + self.amount

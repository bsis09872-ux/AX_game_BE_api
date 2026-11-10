"""
1. 회원은 하나의 지갑을 가지고 있다. 
2. 지갑에 보유하는 금액은 관리자에 의해서 충전이 된다.
3. 입찰시 금액이 묶이고, 낙찰 정산때 차감된다.
4. 금액 변동은 로그로 기록한다.
"""

"""지갑 도메인 객체 (프레임워크 의존 없음)"""
from dataclasses import dataclass
from datetime import datetime
from wallet.domain.exceptions import BalanceLimitExceededError, InsufficientBalanceError
from wallet.domain.rules import MAX_BALANCE
from wallet.domain.service import BalanceEventType, BalanceRecord

@dataclass
class Balance:
    value: int = 0

    # 차감
    def minus(self, amount: int):
        if self.value < amount:
            raise InsufficientBalanceError()
        self.value -= amount

    # 추가 (충전 금액은 입력에서 막아도, 기존 잔액과 더한 값은 넘칠 수 있어 여기서 확인한다)
    def plus(self, amount: int):
        if self.value + amount > MAX_BALANCE:
            raise BalanceLimitExceededError()
        self.value += amount

@dataclass
class Wallet:
    user_id: int
    balance: Balance          # 예약금을 포함한 총잔액
    updated_at: datetime  # balance가 마지막으로 바뀐 시각


    def add_balance(
        self, amount: int, logger: BalanceRecord, event_type: BalanceEventType = "BALANCE_CREDIT"
    ):

        prev_balance = self.balance.value

        self.balance.plus(amount)

        self.logging(prev_balance, logger, event_type)

    def subtract_balance(
        self, amount: int, logger: BalanceRecord, event_type: BalanceEventType = "BALANCE_DEBIT"
    ):

        prev_balance = self.balance.value
        self.balance.minus(amount)

        self.logging(prev_balance, logger, event_type)

    def logging(self, prev_balance: int, logger: BalanceRecord, event_type: BalanceEventType):
        logger.logging(self.user_id, prev_balance, self.balance.value, event_type)
        




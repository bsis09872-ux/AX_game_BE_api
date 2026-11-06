"""
1. 회원은 하나의 지갑을 가지고 있다. 
2. 지갑에 보유하는 금액은 관리자에 의해서 충전이 된다.
3. 입찰시 금액이 차감되고, 유찰시에 복구된다.
4. 금액 변동은 로그로 기록한다.
"""

"""지갑 도메인 객체 (프레임워크 의존 없음)"""
from dataclasses import dataclass
from datetime import datetime
from wallet.domain.exceptions import InsufficientAuthorityError, InsufficientBalanceError
from wallet.domain.service import BalanceRecord

@dataclass
class Balance:
    value: int = 0

    # 차감
    def minus(self, amount: int):
        if self.value < amount:
            raise InsufficientBalanceError()
        self.value -= amount

    # 추가 
    def plus(self, amount: int):
        self.value += amount

@dataclass
class Wallet:
    user_id: int
    balance: Balance          # 예약금을 포함한 총잔액
    updated_at: datetime  # balance가 마지막으로 바뀐 시각


    def add_balance(self, amount: int, logger: BalanceRecord):

        prev_balance = self.balance.value

        self.balance.plus(amount)

        self.logging(prev_balance, logger)

    def subtract_balance(self, amount: int, logger: BalanceRecord):

        prev_balance = self.balance.value
        self.balance.minus(amount)

        self.logging(prev_balance, logger)

    def logging(self, prev_balance: int, logger: BalanceRecord):
        logger.logging(self.user_id, prev_balance, self.balance.value)
        




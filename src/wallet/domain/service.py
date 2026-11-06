from abc import ABC, abstractmethod
from typing import Literal

# 잔액 변경 종류
#   INITIAL_GRANT  가입 시 초기 지급 (WALL-06)
#   PURCHASE_DEBIT 낙찰 정산 구매자 차감 (WALL-08)
#   SALE_CREDIT    낙찰 정산 판매자 지급 (WALL-08)
#   BALANCE_CREDIT 그 밖의 증가 (관리자 충전 등)
#   BALANCE_DEBIT  그 밖의 감소
BalanceEventType = Literal[
    "INITIAL_GRANT", "PURCHASE_DEBIT", "SALE_CREDIT", "BALANCE_CREDIT", "BALANCE_DEBIT"
]


class BalanceRecord(ABC):

    @abstractmethod
    def logging(
        self, user_id: int, prev_balance: int, current_balance: int, event_type: BalanceEventType
    ):
        pass


class RoleCheck(ABC):
    @abstractmethod
    def is_admin(self):
        """인증을 받은 사용자가 관리자인지 체크"""
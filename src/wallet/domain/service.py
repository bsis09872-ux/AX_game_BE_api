"""지갑 도메인 객체(Wallet)가 쓰는 계약 (구현은 infrastructure, 조립은 wiring)

도메인은 이 계약만 알고, 구현체가 무엇을 쓰는지(서버 로그 등)는 모른다.
서비스만 쓰는 다른 도메인 기능의 계약은 application/contracts.py에 있다.
"""
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


# 관리자 여부(RoleCheck)는 도메인 객체가 쓰지 않고 서비스만 쓰는 다른 도메인(users) 기능이라
# 팀 규칙대로 application/contracts.py로 옮겼다.
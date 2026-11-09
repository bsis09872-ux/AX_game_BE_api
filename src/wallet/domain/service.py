"""지갑 도메인이 바깥에 요구하는 계약 (구현은 infrastructure, 조립은 wiring)

도메인과 애플리케이션은 이 계약만 알고, 구현체가 무엇을 쓰는지(로그, users 도메인 등)는 모른다.
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


class RoleCheck(ABC):
    @abstractmethod
    async def is_admin(self, user_id: int) -> bool:
        """해당 회원이 관리자인지 확인한다.

        user_id는 presentation이 인증으로 확인해 넘긴 요청자 ID다.
        회원 정보를 어디서 읽는지는 구현체(infrastructure)가 정한다.
        """
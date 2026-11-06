from abc import ABC, abstractmethod

class BalanceRecord(ABC):

    @abstractmethod
    def logging(self, user_id: int, prev_balance: int, current_balance: int):
        pass


class RoleCheck(ABC):
    @abstractmethod
    def is_admin(self):
        """인증을 받은 사용자가 관리자인지 체크"""
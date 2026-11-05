from abc import ABC, abstractmethod

from users.domain.user import User


class UserRepository(ABC):
    @abstractmethod
    async def find_by_id(self, user_id: int) -> User | None:
        pass

    @abstractmethod
    async def find_by_login_id(self, login_id: str) -> User | None:
        pass

    @abstractmethod
    async def create(self, user: User) -> User:
        pass

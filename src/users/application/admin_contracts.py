from typing import Protocol


class PasswordHasher(Protocol):
    async def hash(self, password: str) -> str: ...


class Transaction(Protocol):
    async def commit(self) -> None: ...

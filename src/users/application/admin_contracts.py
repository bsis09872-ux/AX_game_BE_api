from typing import Protocol
from datetime import datetime


class PasswordHasher(Protocol):
    async def hash(self, password: str) -> str: ...


class Transaction(Protocol):
    async def commit(self) -> None: ...


class SessionRevoker(Protocol):
    async def revoke_all_for_user(self, user_id: int, now: datetime) -> None: ...

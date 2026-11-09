import logging

from shared.core.exceptions import ForbiddenError
from users.application.admin_contracts import PasswordHasher, Transaction
from users.application.service import UserService

logger = logging.getLogger(__name__)


class MemberAdminService:
    def __init__(self, users: UserService, passwords: PasswordHasher, transaction: Transaction):
        self.users = users
        self.repository = users.repository
        self.passwords = passwords
        self.transaction = transaction

    async def _lock_and_authorize(self, actor_id: int, target_id: int | None = None):
        await self.repository.lock_administration()
        members = await self.repository.find_for_update_many([actor_id] + ([target_id] if target_id else []))
        actor = members.get(actor_id)
        if actor is None or not actor.is_active() or actor.role != 'ADMIN':
            raise ForbiddenError()
        return members

    async def create_account(self, actor_id: int, login_id: str, display_name: str, password: str):
        password_hash = await self.passwords.hash(password)
        await self._lock_and_authorize(actor_id)
        user = await self.users.create_user(login_id, display_name, password_hash)
        await self.transaction.commit()
        logger.info('admin_member_created actor_id=%s target_id=%s', actor_id, user.id)
        return user

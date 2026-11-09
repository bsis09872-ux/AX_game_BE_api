import logging

from shared.core.exceptions import ForbiddenError
from users.application.admin_contracts import PasswordHasher, Transaction
from users.application.service import UserService
from users.domain.exceptions import AdminAccountProtectionError, UserNotFoundError

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

    async def change_role(self, actor_id: int, target_id: int, role: str):
        members = await self._lock_and_authorize(actor_id, target_id)
        target = members.get(target_id)
        if target is None or not target.is_active():
            raise UserNotFoundError()
        if role != 'ADMIN' and target.role == 'ADMIN':
            if actor_id == target_id:
                raise AdminAccountProtectionError('자기 계정의 관리자 권한은 해제할 수 없습니다.')
            if await self.repository.count_available_admins() <= 1:
                raise AdminAccountProtectionError()
        target.change_role(role)
        await self.repository.save_admin_settings(target)
        await self.transaction.commit()
        logger.info('admin_member_role_changed actor_id=%s target_id=%s role=%s', actor_id, target_id, role)
        return target

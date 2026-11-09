import logging
from datetime import datetime, timezone

from shared.core.exceptions import ForbiddenError
from users.application.admin_contracts import PasswordHasher, Transaction, SessionRevoker
from users.application.service import UserService
from users.domain.exceptions import AdminAccountProtectionError, UserNotFoundError

logger = logging.getLogger(__name__)


class MemberAdminService:
    def __init__(self, users: UserService, passwords: PasswordHasher, transaction: Transaction, sessions: SessionRevoker):
        self.users = users
        self.repository = users.repository
        self.passwords = passwords
        self.transaction = transaction
        self.sessions = sessions

    async def _lock_and_authorize(self, actor_id: int, target_id: int | None = None):
        await self.repository.lock_administration()
        members = await self.repository.find_for_update_many([actor_id] + ([target_id] if target_id else []))
        actor = members.get(actor_id)
        if actor is None or not actor.can_login() or actor.role != 'ADMIN':
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

    async def set_login_suspension(self, actor_id: int, target_id: int, suspended: bool):
        members = await self._lock_and_authorize(actor_id, target_id)
        target = members.get(target_id)
        if target is None or not target.is_active():
            raise UserNotFoundError()
        if suspended:
            if actor_id == target_id:
                raise AdminAccountProtectionError('자기 계정은 로그인 정지할 수 없습니다.')
            if target.role == 'ADMIN' and target.can_login() and await self.repository.count_available_admins() <= 1:
                raise AdminAccountProtectionError()
        now = datetime.now(timezone.utc)
        target.suspend_login(suspended, now)
        await self.repository.save_admin_settings(target)
        if suspended:
            await self.sessions.revoke_all_for_user(target_id, now)
        await self.transaction.commit()
        logger.info('admin_member_login_status actor_id=%s target_id=%s suspended=%s', actor_id, target_id, suspended)
        return target

    async def set_bid_restriction(self, actor_id: int, target_id: int, until: datetime | None):
        members = await self._lock_and_authorize(actor_id, target_id)
        target = members.get(target_id)
        if target is None or not target.is_active():
            raise UserNotFoundError()
        target.restrict_bidding(until, datetime.now(timezone.utc))
        await self.repository.save_admin_settings(target)
        await self.transaction.commit()
        logger.info('admin_member_bid_restriction actor_id=%s target_id=%s', actor_id, target_id)
        return target

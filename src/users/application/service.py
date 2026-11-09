# 회원 조회와 생성을 담당한다.

import logging
from datetime import datetime

from users.domain.repository import UserRepository
from users.domain.user import User
from users.domain.exceptions import UserNotFoundError, LoginIdAlreadyExistsError

from users.application.dto import UserSummary

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    async def list_members(self, query: str = '', role: str | None = None, page: int = 1, size: int = 20):
        return await self.repository.list_members(query, role, page, size)

    # ID에 해당하는 회원이 없으면 UserNotFoundError를 발생시키고, 저장소 오류는 그대로 전파한다.
    async def get_user(self, user_id: int) -> User:
        result = await self.repository.find_by_id(user_id=user_id)
        if result is None:
            raise UserNotFoundError("해당 ID의 유저가 존재하지 않습니다.")
        # 조회 로그에는 비밀번호 해시 등 회원 정보가 노출되지 않도록 ID만 남긴다.
        logger.debug(f"회원 조회 성공 user_id={user_id}")
        return result

    # 인증 어댑터가 로그인 ID로 조회하며 없는 계정의 처리는 인증 서비스가 결정한다.
    async def find_by_login_id(self, login_id: str) -> User | None:
        return await self.repository.find_by_login_id(login_id)

    async def find_by_login_id_for_update(self, login_id: str) -> User | None:
        return await self.repository.find_by_login_id_for_update(login_id)

    # 다른 도메인에 필요한 회원 상태만 전달하며 탈퇴 회원도 조회 결과에 포함한다.
    async def get_user_summary(self, user_id: int) -> UserSummary:
        user = await self.get_user(user_id=user_id)

        return self._summary(user)

    @staticmethod
    def _summary(user: User) -> UserSummary:

        # 저장된 회원의 ID 누락은 내부 조회 결과 오류다.
        if user.id is None:
            raise RuntimeError("회원 조회 결과에 ID가 없습니다.")

        return UserSummary(
            id=user.id,
            display_name=user.display_name,
            is_active=user.is_active(),
            auction_blocked_until=user.auction_blocked_until,
            role=user.role,
            auction_purchase_count=user.auction_purchase_count,
        )

    async def get_for_update_many(self, user_ids: list[int]) -> dict[int, UserSummary]:
        users = await self.repository.find_for_update_many(user_ids)
        # 없는 ID는 생략한다. 탈퇴 여부는 호출자가 is_active로 구분한다.
        return {user_id: self._summary(user) for user_id, user in users.items()}

    async def update_auction_limit(
        self, user_id: int, purchase_count: int, blocked_until: datetime | None,
    ) -> None:
        users = await self.repository.find_for_update_many([user_id])
        user = users.get(user_id)
        if user is None or not user.is_active():
            raise UserNotFoundError()
        user.update_auction_limit(purchase_count, blocked_until)
        # 여러 회원을 변경할 때는 호출자가 먼저 ID 오름차순으로 일괄 잠근다.
        await self.repository.save_auction_limit(user)


    async def create_user(
        self, login_id: str, display_name: str, password_hash: str
    ) -> User:
        existing_user = await self.repository.find_by_login_id(login_id=login_id)
        if existing_user is not None:
            raise LoginIdAlreadyExistsError()

        user = User(
            login_id=login_id, password_hash=password_hash, display_name=display_name
        )
        # 저장소는 flush까지 수행하며, 최종 commit은 가입 절차를 조율하는 호출자가 맡는다.
        return await self.repository.create(user=user)

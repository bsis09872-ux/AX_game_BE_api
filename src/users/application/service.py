# 회원 조회 유스케이스를 담당하며, 저장소의 조회 결과가 없으면 UserNotFoundError로 처리한다.

import logging

from users.domain.repository import UserRepository, User
from users.domain.exceptions import UserNotFoundError

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    async def get_user(self, user_id: int) -> User:
        result = await self.repository.find_by_id(user_id=user_id)
        if result is None:
            raise UserNotFoundError("해당 ID의 유저가 존재하지 않습니다.")
        logger.debug(f"회원 조회 성공 user_id={user_id}")
        return result

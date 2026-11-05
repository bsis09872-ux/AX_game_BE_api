# 회원 조회 유스케이스를 담당한다.

import logging

from users.domain.repository import UserRepository, User
from users.domain.exceptions import UserNotFoundError

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    # ID에 해당하는 회원이 없으면 UserNotFoundError를 발생시키고, 저장소 오류는 그대로 전파한다.
    async def get_user(self, user_id: int) -> User:
        result = await self.repository.find_by_id(user_id=user_id)
        if result is None:
            raise UserNotFoundError("해당 ID의 유저가 존재하지 않습니다.")
        # 조회 로그에는 비밀번호 해시 등 회원 정보가 노출되지 않도록 ID만 남긴다.
        logger.debug(f"회원 조회 성공 user_id={user_id}")
        return result

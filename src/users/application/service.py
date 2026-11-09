# 회원 조회와 생성을 담당한다.

import logging

from users.domain.repository import UserRepository
from users.domain.user import User
from users.domain.exceptions import UserNotFoundError, LoginIdAlreadyExistsError

from users.application.dto import UserSummary

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

    # 인증 어댑터가 로그인 ID로 조회하며 없는 계정의 처리는 인증 서비스가 결정한다.
    async def find_by_login_id(self, login_id: str) -> User | None:
        return await self.repository.find_by_login_id(login_id)

    # 다른 도메인에 필요한 회원 상태만 전달하며 탈퇴 회원도 조회 결과에 포함한다.
    async def get_user_summary(self, user_id: int) -> UserSummary:
        user = await self.get_user(user_id=user_id)

        # 저장된 회원의 ID 누락은 내부 조회 결과 오류다.
        if user.id is None:
            raise RuntimeError("회원 조회 결과에 ID가 없습니다.")

        return UserSummary(
            id=user.id,
            display_name=user.display_name,
            is_active=user.is_active(),
            auction_blocked_until=user.auction_blocked_until,
            role=user.role,
        )


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

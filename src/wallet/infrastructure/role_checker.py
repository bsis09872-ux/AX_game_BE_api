"""RoleCheck 구현: users 도메인의 회원 정보로 관리자 여부를 판단한다.

application/contracts.py의 RoleCheck 모양을 맞춘다 (계약 파일은 import하지 않는다: 구조적 타이핑).
지갑 코드 중 users 도메인을 import하는 곳은 이 파일(구현)과 wiring.py(조립) 둘뿐이다.
users가 공개한 UserService만 쓰고, 회원 엔티티에서는 role 외의 필드를 쓰지 않는다.
users에 role 조회 계약(예: UserSummary.role)이 생기면 이 파일만 바꾼다.

role 값은 users.role ('USER' | 'ADMIN')과 같다.
"""
from users.application.service import UserService

ADMIN_ROLE = "ADMIN"


class UserRoleCheck:
    def __init__(self, user_service: UserService) -> None:
        self._user_service = user_service

    async def is_admin(self, user_id: int) -> bool:
        # 회원이 없으면 users의 UserNotFoundError(404)가 그대로 올라간다.
        # 인증을 통과한 요청자라 실제로는 생기지 않는다.
        user = await self._user_service.get_user(user_id)
        return user.role == ADMIN_ROLE

"""RoleCheck 구현: 요청한 사용자의 역할로 관리자 여부를 판단한다.

is_admin()에 인자가 없으므로, 요청마다 인증된 사용자의 role을 생성자로 받는다.
role 값은 users.role ('USER' | 'ADMIN')과 같다.
auth 연결 전에는 actor_role=None → 항상 관리자 아님.
"""
from wallet.domain.service import RoleCheck

ADMIN_ROLE = "ADMIN"


class RoleCheckImpl(RoleCheck):
    def __init__(self, actor_role: str | None = None) -> None:
        self._actor_role = actor_role

    def is_admin(self) -> bool:
        """인증을 받은 사용자가 관리자인지 체크"""
        return self._actor_role == ADMIN_ROLE

import re
from datetime import datetime

from users.domain.exceptions import InvalidUserError


class User:
    def __init__(
        self,
        login_id: str,
        password_hash: str,
        *,
        display_name: str,
        user_id: int | None = None,
        role: str = "USER",
        auction_purchase_count: int = 0,
        auction_blocked_until: datetime | None = None,
        deleted_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        if re.fullmatch(string=login_id, pattern=r"[a-z0-9_]{4,50}") is None:
            raise InvalidUserError("로그인 ID는 소문자, 숫자, 밑줄로 4~50자여야 합니다.")

        if not password_hash.strip():
            raise InvalidUserError("비밀번호 해시가 필요합니다.")

        if role not in ("USER", "ADMIN"):
            raise InvalidUserError("유효하지 않은 회원 역할입니다.")

        self.id = user_id
        self.login_id = login_id
        self.password_hash = password_hash
        self.display_name = display_name
        self.role = role
        self.auction_purchase_count = auction_purchase_count
        self.auction_blocked_until = auction_blocked_until
        self.deleted_at = deleted_at
        self.created_at = created_at
        self.updated_at = updated_at

    def is_active(self) -> bool:
        return self.deleted_at is None

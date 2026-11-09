# 회원 식별 정보와 계정 상태를 보관하고 로그인 ID, 비밀번호 해시, 역할의 유효성을 검사한다.
import re
from datetime import datetime

from users.domain.exceptions import InvalidUserError


# 신규 회원 생성과 저장된 회원 복원을 함께 지원한다.
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
        manual_auction_blocked_until: datetime | None = None,
        login_suspended_at: datetime | None = None,
        deleted_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        # ID는 4~50자의 소문자/숫자/밑줄만 허용하며 입력을 자동 변환하지 않는다.
        if re.fullmatch(string=login_id, pattern=r"[a-z0-9_]{4,50}") is None:
            raise InvalidUserError("로그인 ID는 소문자, 숫자, 밑줄로 4~50자여야 합니다.")

        # 거래 기록의 이름 스냅샷 길이와 맞추며 공백뿐인 표시 이름은 허용하지 않는다.
        if not display_name.strip() or not 2 <= len(display_name) <= 50:
            raise InvalidUserError("표시 이름은 공백이 아닌 문자를 포함한 2~50자여야 합니다.")

        # 해시의 누락만 검사하고 원본은 보존한다. 실제 해싱은 별도 구현이 담당한다.
        if not password_hash.strip():
            raise InvalidUserError("비밀번호 해시가 필요합니다.")

        # 도메인은 역할의 허용 값을 검사한다. 가입 요청에서의 역할 지정은 입력 스키마가 막는다.
        if role not in ("USER", "ADMIN"):
            raise InvalidUserError("유효하지 않은 회원 역할입니다.")

        # DB에서 전달한 ID와 역할, 탈퇴 시각을 그대로 보존한다.
        self.id = user_id
        self.login_id = login_id
        self.password_hash = password_hash
        self.display_name = display_name
        self.role = role
        self.auction_purchase_count = auction_purchase_count
        self.auction_blocked_until = auction_blocked_until
        self.manual_auction_blocked_until = manual_auction_blocked_until
        self.login_suspended_at = login_suspended_at
        self.deleted_at = deleted_at
        self.created_at = created_at
        self.updated_at = updated_at

    # 탈퇴 시각이 없으면 활성 회원이다. 인증과 권한 검사는 이 상태를 참고한다.
    def is_active(self) -> bool:
        return self.deleted_at is None

    def change_role(self, role: str) -> None:
        if role not in ('USER', 'ADMIN'):
            raise InvalidUserError('유효하지 않은 회원 역할입니다.')
        self.role = role

    def can_login(self) -> bool:
        return self.is_active() and self.login_suspended_at is None

    @property
    def effective_auction_blocked_until(self) -> datetime | None:
        deadlines = [value for value in (self.auction_blocked_until, self.manual_auction_blocked_until) if value is not None]
        return max(deadlines) if deadlines else None

    def suspend_login(self, suspended: bool, now: datetime) -> None:
        if type(suspended) is not bool or now.utcoffset() is None:
            raise InvalidUserError('로그인 정지 상태와 시각을 확인해 주세요.')
        self.login_suspended_at = (self.login_suspended_at or now) if suspended else None

    def restrict_bidding(self, until: datetime | None, now: datetime) -> None:
        if until is not None and (until.utcoffset() is None or until <= now):
            raise InvalidUserError('입찰 제한 종료 시각은 시간대가 있는 미래 시각이어야 합니다.')
        self.manual_auction_blocked_until = until

    def update_auction_limit(self, purchase_count: int, blocked_until: datetime | None) -> None:
        if type(purchase_count) is not int or not 0 <= purchase_count <= 2147483647:
            raise InvalidUserError("낙찰 횟수는 0 이상의 정수여야 합니다.")
        if blocked_until is not None and blocked_until.utcoffset() is None:
            raise InvalidUserError("입찰 제한 종료 시각에 시간대 정보가 필요합니다.")
        self.auction_purchase_count = purchase_count
        self.auction_blocked_until = blocked_until

    # 제한 종료 시각 이전에만 입찰 제한으로 판단한다. 탈퇴 상태는 별도 검사한다.
    def is_auction_blocked(self, now: datetime) -> bool:
        if now.utcoffset() is None:
            raise ValueError("현재 시각에 시간대 정보가 없습니다.")
        blocked_until = self.effective_auction_blocked_until
        if blocked_until is None:
            return False
        if blocked_until.utcoffset() is None:
            raise RuntimeError("입찰 제한 종료 시각에 시간대 정보가 없습니다.")
        return now < blocked_until

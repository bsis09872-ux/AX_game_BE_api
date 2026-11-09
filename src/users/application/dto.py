# 다른 도메인에 제공하는 회원 조회 결과를 정의한다.

from dataclasses import dataclass
from datetime import datetime

# 조회 시점의 회원 정보이며 거래 체결 시 display_name을 스냅샷에 복사할 수 있다.
@dataclass(frozen=True)
class UserSummary:
    id: int
    display_name: str
    is_active: bool
    # None은 제한 시각 없음. 현재 제한 여부는 종료 시각과 현재 시각을 비교해 판단한다.
    auction_blocked_until: datetime | None
    role: str

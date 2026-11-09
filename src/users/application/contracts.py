from datetime import datetime
from typing import Protocol

from users.application.dto import UserSummary


class AuctionMemberGateway(Protocol):
    """회원 서비스가 경매에 제공하는 조회, 잠금과 자동 제한 저장 계약."""

    # auction_blocked_until은 기존 자동 제한 시각이다.
    # 입찰 허용 여부는 effective_auction_blocked_until과 현재 시각을 비교한다.
    # manual_auction_blocked_until은 관리자 설정이며 경매 정책 계산에 사용하지 않는다.
    async def get_user_summary(self, user_id: int) -> UserSummary: ...

    # ID 오름차순 잠금. 없는 ID는 생략하고 탈퇴 회원은 is_active=False로 반환한다.
    async def get_for_update_many(self, user_ids: list[int]) -> dict[int, UserSummary]: ...

    # 자동 제한과 횟수만 저장/flush한다. 관리자 제한은 변경하지 않으며 commit은 호출자 책임이다.
    async def update_auction_limit(self, user_id: int, purchase_count: int, blocked_until: datetime | None) -> None: ...

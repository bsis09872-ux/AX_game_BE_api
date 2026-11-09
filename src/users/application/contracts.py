from datetime import datetime
from typing import Protocol

from users.application.dto import UserSummary


class AdminRoleChecker(Protocol):
    """인증된 회원 ID로 관리자 기능 사용 가능 여부를 조회한다."""

    # 없는 회원, USER, 탈퇴 또는 로그인 정지 회원은 False. 조회 실패는 예외로 전파한다.
    # 토큰과 로그인 세션 검증은 호출 전에 auth에서 수행한다.
    async def is_admin(self, user_id: int) -> bool: ...


class MemberWalletProvisioner(Protocol):
    """회원 생성 트랜잭션에서 지갑 담당 구현에 요청할 계약."""

    # TODO(지갑 담당): 현재 기준 브랜치에는 구현이 없다. 같은 요청 세션으로 지갑을
    # 생성하고 flush까지만 수행해야 한다. 실패는 전파해 회원과 함께 rollback한다.
    # 반환값은 지갑 담당의 객체이며 회원 기능에서는 내용을 해석하지 않는다.
    async def create_wallet(self, user_id: int) -> object: ...


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

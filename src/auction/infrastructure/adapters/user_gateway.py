# User Adapter: 경매의 AuctionUserGateway 계약을 users 서비스에 연결한다.
# users가 다른 도메인에 공개한 메서드만 호출하고 모델·테이블을 직접 읽지 않는다.
# 낙찰 횟수 계산과 제한 판단은 경매 정책이 한다. 이 Adapter는 조회·저장만 전달한다.
# commit·rollback은 트랜잭션 담당자가 한다.
#
# [TO DO][요청 → users] get_user_summary(user_id) -> UserSummary에 auction_purchase_count 추가
# 용도: 입찰·정산 전 사용자의 저장된 낙찰 횟수를 조회한다.
# [TO DO][요청 → users] get_for_update_many(user_ids: list[int]) -> 사용자별 경매 상태 (ID 오름차순 잠금)
# 용도: 정산 시 판매자·구매자를 합의한 잠금 순서로 잠근다.
# [TO DO][요청 → users] update_auction_limit(user_id, purchase_count, blocked_until) -> None (flush까지만)
# 용도: 낙찰 후 계산한 횟수·제한 종료 시각을 저장한다.

from datetime import datetime

from auction.application.contract import AuctionUserGateway
from auction.application.dto import AuctionUserState
from users.application.service import UserService
from users.domain.exceptions import UserNotFoundError

class AuctionUserGatewayAdapter(AuctionUserGateway):

    def __init__(self, user_service: UserService) -> None:
        self._user_service = user_service

    # 사용자 제한 상태 조회. 사용자가 없으면 None
    async def get_state(
        self,
        user_id: int,
    ) -> AuctionUserState | None:
        raise NotImplementedError("users의 낙찰 횟수 조회 제공 후 연결한다.")

    # 여러 사용자 잠금 조회 (ID 오름차순)
    async def get_for_update_many(
        self,
        user_ids: list[int],
    ) -> dict[int, AuctionUserState]:
        raise NotImplementedError("users의 잠금 조회 제공 후 연결한다.")

    # 낙찰 횟수·제한 종료 시각 저장
    async def update_limit(
        self,
        user_id: int,
        purchase_count: int,
        blocked_until: datetime | None,
    ) -> None:
        raise NotImplementedError("users의 제한 상태 저장 제공 후 연결한다.")

    # 거래 기록용 이름 조회. 없는 사용자는 결과에서 뺀다.
    async def get_display_names(
        self,
        user_ids: list[int],
    ) -> dict[int, str]:
        names: dict[int, str] = {}
        for user_id in set(user_ids):
            try:
                summary = await self._user_service.get_user_summary(user_id)
            except UserNotFoundError:
                continue
            names[user_id] = summary.display_name
        return names

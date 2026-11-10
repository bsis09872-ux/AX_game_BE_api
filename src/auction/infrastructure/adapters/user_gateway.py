# User Adapter: 경매의 AuctionUserGateway 계약을 users 서비스에 연결한다.
# users가 다른 도메인에 공개한 메서드만 호출하고 모델·테이블을 직접 읽지 않는다.
# 낙찰 횟수 계산과 제한 판단은 경매 정책이 한다. 이 Adapter는 조회·저장만 전달한다.
# commit·rollback은 트랜잭션 담당자가 한다.
#
# 사용하는 users 메서드
# get_user_summary(user_id): 사용자의 저장된 낙찰 횟수·제한 상태·이름 조회
# get_for_update_many(user_ids): 입찰·정산 시 사용자를 ID 오름차순으로 잠금 조회
# update_auction_limit(user_id, purchase_count, blocked_until): 낙찰 후 제한 상태 저장 (flush까지만)
# is_admin(user_id): 관리자 기능 사용 가능 여부 조회

from datetime import datetime

from auction.application.contract import AuctionUserGateway
from auction.application.dto import AuctionUserState
from users.application.service import UserService
from users.domain.exceptions import UserNotFoundError

class AuctionUserGatewayAdapter(AuctionUserGateway):

    def __init__(self, user_service: UserService) -> None:
        self._user_service = user_service

    # 사용자 ID로 회원 정보를 조회하고 경매용 DTO로 변환한다.
    # 없는 사용자는 None을 반환하고, DB 오류 등은 호출 측에 전달한다.
    async def get_state(
        self,
        user_id: int,
    ) -> AuctionUserState | None:
        try:
            summary = await self._user_service.get_user_summary(user_id)
        except UserNotFoundError:
            return None

        return AuctionUserState(
            user_id=summary.id,
            purchase_count=summary.auction_purchase_count,
            blocked_until=summary.auction_blocked_until,
            effective_blocked_until=summary.effective_auction_blocked_until,
            is_active=summary.is_active,
        )

    # 사용자 ID 목록을 받아 User 서비스에 ID 오름차순 잠금 조회를 요청한다.
    # 조회 결과를 경매용 DTO로 변환한다. 없는 ID는 결과에서 제외된다.
    # 잠금은 여기서 해제하지 않고 트랜잭션의 commit·rollback까지 유지한다.
    async def get_for_update_many(
        self,
        user_ids: list[int],
    ) -> dict[int, AuctionUserState]:
        summaries = await self._user_service.get_for_update_many(user_ids)

        return {
            user_id: AuctionUserState(
                user_id=summary.id,
                purchase_count=summary.auction_purchase_count,
                blocked_until=summary.auction_blocked_until,
                effective_blocked_until=summary.effective_auction_blocked_until,
                is_active=summary.is_active,
            )
            for user_id, summary in summaries.items()
        }

    # 사용자 ID와 경매에서 계산한 낙찰 횟수·자동 제한 시각을 전달한다.
    # 관리자 수동 제한은 변경하지 않는다. 반환값은 없다.
    # 저장 오류는 전달하고, commit·rollback은 호출 측에서 처리한다.
    async def update_limit(
        self,
        user_id: int,
        purchase_count: int,
        blocked_until: datetime | None,
    ) -> None:
        await self._user_service.update_auction_limit(
            user_id=user_id,
            purchase_count=purchase_count,
            blocked_until=blocked_until,
        )

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

    # 인증된 사용자 ID로 관리자 기능 사용 가능 여부를 조회한다.
    # User가 현재 회원 상태와 권한을 검사하고 True 또는 False를 반환한다.
    # 조회 오류는 호출 측에 전달한다.
    async def is_admin(self, user_id: int) -> bool:
        return await self._user_service.is_admin(user_id)

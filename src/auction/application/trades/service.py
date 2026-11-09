# Service: 사용자의 거래 내역과 현재 입찰 제한 상태를 조회한다.
# Trade는 확정 기록이므로 수정·삭제하는 기능을 제공하지 않는다.
# [TO DO] 다음 PR에서 AuctionUserGateway 구현체를 연결한다.
# [TO DO] 조립부에서 같은 요청의 Repository와 사용자 조회 구현체를 주입한다.
# 현재 조회 로직은 작성되어 있지만 실제 User 연동은 완료되지 않았다.

from datetime import datetime, timedelta

from auction.application.contract import AuctionUserGateway
from auction.domain.trades.entities import Trade
from auction.domain.trades.policies import (
    AuctionLimitState,
    WIN_LIMIT_WINDOW,
    get_limit_state,
)
from auction.domain.trades.repositories import TradeRepository
from shared.core.exceptions import BusinessRuleError, ForbiddenError, NotFoundError

class TradeService:
    # 거래 기록과 사용자 제한 정보를 조회할 기능을 전달받는다.
    def __init__(
        self,
        trades: TradeRepository,
        user_limit_reader: AuctionUserGateway,
    ):
        self.trades = trades
        self.user_limit_reader = user_limit_reader

    # 내가 "낙찰받은" 거래를 최신순으로 가져온다.
    async def get_my_purchases(
        self,
        buyer_id: int,
        page: int,
    ) -> list[Trade]:
        return await self.trades.list_by_buyer(buyer_id, page)

    # 내가 "판매한" 거래를 최신순으로 가져온다.
    async def get_my_sales(
        self,
        seller_id: int,
        page: int,
    ) -> list[Trade]:
        return await self.trades.list_by_seller(seller_id, page)

    # 인증된 요청자 ID와 조회 조건을 받아 관리자 권한을 확인한다.
    # 관리자이면 조건에 맞는 거래 내역을 페이지별로 반환한다.
    # 조회만 수행하며 거래 기록 변경과 commit은 하지 않는다.
    async def get_admin_trades(
        self,
        requester_id: int,
        page: int,
        *,
        listing_id: int | None = None,
        buyer_id: int | None = None,
        seller_id: int | None = None,
    ) -> list[Trade]:
        if not await self.user_limit_reader.is_admin(requester_id):
            raise ForbiddenError("관리자만 전체 거래 내역을 조회할 수 있습니다.")

        if page < 1:
            raise BusinessRuleError("페이지 번호는 1 이상이어야 합니다.")

        return await self.trades.list_filtered(
            page=page,
            listing_id=listing_id,
            buyer_id=buyer_id,
            seller_id=seller_id,
        )

    # 사용자 ID와 현재 시각으로 낙찰 횟수와 최종 입찰 제한 상태를 조회한다.
    # 횟수는 자동 제한 정책으로 계산하고, 제한 여부에는 관리자 제한도 반영한다.
    # 화면에 표시할 결과를 반환하며 DB 값은 변경하지 않는다.
    async def get_bid_limit_status(
        self,
        user_id: int,
        now: datetime,
    ) -> AuctionLimitState:
        user_state = await self.user_limit_reader.get_state(user_id)
        if user_state is None or not user_state.is_active:
            raise NotFoundError("활성 사용자를 찾을 수 없습니다.")

        # 자동 제한 상태를 계산한다. 관리자 제한은 집계 기준에 넣지 않는다.
        state = get_limit_state(
            win_times=[],
            blocked_until=user_state.blocked_until,
            now=now,
        )

        # 자동 제한 중이 아니면 실제 기록으로 유효 낙찰 횟수를 계산한다.
        if not state.is_blocked:
            win_times = await self.trades.find_win_times_between(
                buyer_id=user_id,
                since=now - WIN_LIMIT_WINDOW,
                until=now,
            )
            state = get_limit_state(
                win_times=win_times,
                blocked_until=user_state.blocked_until,
                now=now,
            )

        # 화면의 제한 여부와 남은 시간에는 최종 제한 시각을 사용한다.
        blocked_until = user_state.effective_blocked_until
        remaining = timedelta(0)
        if blocked_until is not None:
            remaining = max(blocked_until - now, timedelta(0))

        # 조회 응답용 결과다. 자동 제한 저장값으로 사용하지 않는다.
        return AuctionLimitState(
            purchase_count=state.purchase_count,
            max_count=state.max_count,
            blocked_until=blocked_until,
            is_blocked=remaining > timedelta(0),
            remaining=remaining,
        )
# Service: 사용자의 거래 내역과 현재 입찰 제한 상태를 조회한다.
# Trade는 확정 기록이므로 수정·삭제하는 기능을 제공하지 않는다.

from datetime import datetime

from auction.domain.trades.entities import Trade
from auction.domain.trades.policies import AuctionLimitState, WIN_LIMIT_WINDOW, get_limit_state
from auction.domain.trades.repositories import TradeRepository

#추후 받을 기능 임의로 정의해두고 불러옴 (수정예정)
from auction.application.contract import AuctionUserGateway

from shared.core.exceptions import NotFoundError

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

        # 경매 참여 화면에서 현재 낙찰 횟수와 입찰 제한 시간을 확인한다.
    async def get_bid_limit_status(
        self,
        user_id: int,
        now: datetime,
    ) -> AuctionLimitState:
        # 사용자 정보는 계약을 통해 받고, User 모델을 직접 참조하지 않는다.
        user_state = await self.user_limit_reader.get_state(user_id)

        if user_state is None:
            raise NotFoundError("사용자를 찾을 수 없습니다.")

        # 시간값을 검증하고, 현재 제한 중이면 남은 시간을 바로 반환한다.
        state = get_limit_state(
            win_times=[],
            blocked_until=user_state.blocked_until,
            now=now,
        )
        if state.is_blocked:
            return state

        # 저장된 횟수 대신 최근 30분의 실제 낙찰 기록을 가져온다.
        win_times = await self.trades.find_win_times_between(
            buyer_id=user_id,
            since=now - WIN_LIMIT_WINDOW,
            until=now,
        )

        # 이전 차단 종료 전 기록을 제외하는 규칙은 도메인 정책이 판단한다.
        return get_limit_state(
            win_times=win_times,
            blocked_until=user_state.blocked_until,
            now=now,
        )
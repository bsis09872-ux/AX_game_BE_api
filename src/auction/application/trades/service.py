# Service: 사용자의 거래 내역과 현재 입찰 제한 상태를 조회한다.
# Trade는 확정 기록이므로 수정·삭제하는 기능을 제공하지 않는다.

from datetime import datetime

from auction.domain.trades.entities import Trade
from auction.domain.trades.policies import AuctionLimitState
from auction.domain.trades.repositories import TradeRepository

from shared.core.exceptions import NotFoundError

class TradeService:
    def __init__(self, trades: TradeRepository):
        self.trades = trades

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

    # 경매 참여 화면에서 현재 횟수와 새 입찰 상태를 확인한다.
    async def get_bid_limit_status(
            self,
            user_id: int,
            now: datetime,
    ) -> AuctionLimitState:
        async def get_bid_limit_status(
            self,
            user_id: int,
            now: datetime,
        ) -> AuctionLimitState:

            # User 데이터 조회 (계약명은 예시)
            user_state = await self.user_limit_reader.get_state(user_id)

            if user_state is None:
                raise NotFoundError("사용자를 찾을 수 없습니다.")

            # Auction 정책에서 현재 상태 계산
            return calculate_bid_limit_state(
                purchase_count=user_state.auction_purchase_count,
                blocked_until=user_state.auction_blocked_until,
                now=now,
            )
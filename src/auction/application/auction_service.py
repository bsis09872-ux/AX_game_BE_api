# [경매 주요 처리 기능] 마감된 매물의 정산·거래 생성·낙찰 제한 갱신·다음 매물 공개를 조율한다.
# 스케줄러는 이 서비스를 호출하며 이 파일에서 타이머나 SQL을 실행하지 않는다.
# [도메인 계층 역할] 매물 규칙은 Listing, 거래 기록은 Trade, 제한 계산은 policies에 맡긴다.
#
# 확정 정책: 최근 30분 내 3회 낙찰 시 15분간 새 입찰 제한.
# 제한 중에도 기존 입찰의 정산은 허용하고, 제한 종료 시각은 연장하지 않는다.
#
# 다른 도메인에 요청하는 기능(users·wallet·inventory)과 트랜잭션·잠금 순서 합의는 contract.py 상단 TODO를 따른다.
#
# [TO DO][제공 → 스케줄러 담당] AuctionService.close_expired(now: datetime) -> int
#         용도: 마감 시각이 지난 매물을 종료하고 처리한 건수를 반환한다. 주기적으로 호출해 달라고 요청한다.


import logging
from datetime import datetime

from auction.application.contract import (
    AuctionUserGateway,
    InventoryGateway,
    TransactionManager,
    WalletGateway,
)
from auction.domain.listings.entities import Listing, ListingStatus
from auction.domain.listings.repositories import ListingRepository
from auction.domain.trades.entities import Trade
from auction.domain.trades.policies import WIN_LIMIT_WINDOW, calculate_limit_after_win
from auction.domain.trades.repositories import TradeRepository

logger = logging.getLogger(__name__)


class AuctionService:
    def __init__(
        self,
        listings: ListingRepository,
        trades: TradeRepository,
        users: AuctionUserGateway,
        wallets: WalletGateway,
        inventory: InventoryGateway,
        tx: TransactionManager,
    ):
        self.listings = listings
        self.trades = trades
        self.users = users
        self.wallets = wallets
        self.inventory = inventory
        self.tx = tx

    # [제공 → 스케줄러] 마감 시각이 지난 BIDDING 매물을 찾아 하나씩 종료한다.
    # 매물 1건 = 트랜잭션 1개. 한 건이 실패해도 이미 끝난 다른 매물의 정산은 유지된다.
    # 반환값: 이번 호출에서 실제로 종료한 매물 수.
    async def close_expired(self, now: datetime) -> int:
        # 후보 조회: 잠금 없이 가볍게 조회한다. 실제 처리는 _close_one에서 잠금 재조회 후 한다.
        candidates = await self.listings.list_expired_bidding(now)
        closed = 0

        for candidate in candidates:
            try:
                if await self._close_one(candidate.id, now):
                    await self.tx.commit()
                    closed += 1
                else:
                    # 건너뛴 매물: 바뀐 내용이 없으므로 rollback으로 잠금만 해제한다.
                    await self.tx.rollback()
            except Exception:
                # 기술적 오류: 이 매물의 변경을 전부 되돌린다. 오류를 이유로 유찰 처리하지 않는다.
                # 매물이 BIDDING으로 남으므로 다음 호출 때 다시 후보가 되어 재시도된다.
                # [TO DO][합의 → 전체] 실패 시 계속 처리할지, 호출 측에 예외를 전달할지 확정 후 수정한다.
                await self.tx.rollback()
                logger.exception("매물 마감 처리 실패: listing_id=%s", candidate.id)

        return closed

    # 매물 1건 종료: 잠금 재조회 → 입찰자 유무에 따라 낙찰/유찰 → 같은 종류의 다음 매물 공개.
    # 반환값: 종료했으면 True, 건너뛰었으면 False.
    async def _close_one(self, listing_id: int, now: datetime) -> bool:
        listing = await self.listings.get_for_update(listing_id)

        # 조회와 잠금 사이에 다른 작업이 먼저 종료했거나, 아직 마감 전이면 건너뛴다.
        if listing is None:
            return False
        if listing.status != ListingStatus.BIDDING or not listing.is_expired(now):
            return False

        # 입찰자 있음 → 낙찰 정산(_settle), 없음 → 유찰(_fail)
        # [TO DO] _settle·_open_next는 아직 이 파일에 없다. 요청 계약 확정 후 작성한다.
        if listing.has_bidder():
            await self._settle(listing, now)
        else:
            await self._fail(listing, now)

        await self._open_next(listing.item_definition_id, now)
        return True

    # 유찰: 입찰자가 없거나 정산할 수 없을 때 매물을 FAILED로 바꾸고 아이템 예약을 해제한다.
    # 요청 계약: InventoryGateway.release (상단 [요청 → inventory] 참고)
    async def _fail(self, listing: Listing, now: datetime) -> None:
        listing.mark_failed(now)
        await self.inventory.release(
            inventory_item_id=listing.inventory_item_id,
            owner_id=listing.seller_id,
            listing_id=listing.id,
            now=now,
        )
        await self.listings.save(listing)

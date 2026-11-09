# [경매 주요 처리 기능] 마감된 매물의 정산·거래 생성·낙찰 제한 갱신·다음 매물 공개를 조율한다.
# 스케줄러는 이 서비스를 호출하며 이 파일에서 타이머나 SQL을 실행하지 않는다.
# [도메인 계층 역할] 매물 규칙은 Listing, 거래 기록은 Trade, 제한 계산은 policies에 맡긴다.
#
# 확정 정책: 최근 30분 내 3회 낙찰 시 15분간 새 입찰 제한.
# 제한 중에도 기존 입찰의 정산은 허용하고, 제한 종료 시각은 연장하지 않는다.
#
# 잠금 순서: 매물 → 아이템 종류 → 다음 대기 매물 → 아이템 → 사용자 → 지갑.
# 매물 1건의 종료·정산·다음 매물 공개는 한 트랜잭션이며, 실패하면 함께 rollback한다.
#
# [TO DO][제공 → 스케줄러 담당] open_auction_service()로 close_expired(now)를 주기 실행에 등록한다. (진행 전)
# [TO DO] 낙찰자 탈퇴·아이템 누락 등 재시도해도 실패할 오류를 유찰·수동 확인으로 구분한다. (진행 전)

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
from shared.core.exceptions import NotFoundError

logger = logging.getLogger(__name__)

# 거래 기록에 남길 이름을 찾지 못했을 때 쓰는 표시값이다.
UNKNOWN_NAME = "알 수 없음"


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
    # 입력: 처리 기준 시각(UTC). 반환: 이번 호출에서 실제로 종료한 매물 수.
    # 매물 1건 = 트랜잭션 1개. 한 건이 실패해도 이미 끝난 다른 매물의 정산은 유지된다.
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
                # 현재 매물의 변경을 모두 되돌리고 실패 원인을 기록한다.
                # 매물은 BIDDING으로 남아 다음 주기에 다시 시도한다.
                await self.tx.rollback()
                logger.exception(
                    "매물 마감 처리 실패: listing_id=%s",
                    candidate.id,
                )

        return closed

    # 매물 1건 종료: 잠금 재조회 → 종류 잠금 → 다음 대기 매물 잠금 → 낙찰/유찰 → 다음 매물 공개.
    # 입력: 매물 ID·처리 시각. 반환: 종료했으면 True, 건너뛰었으면 False.
    # commit은 호출자(close_expired)가 한다.
    async def _close_one(self, listing_id: int, now: datetime) -> bool:
        listing = await self.listings.get_for_update(listing_id)

        # 조회와 잠금 사이에 다른 작업이 먼저 종료했거나, 아직 마감 전이면 건너뛴다.
        if listing is None:
            return False
        if listing.status != ListingStatus.BIDDING or not listing.is_expired(now):
            return False

        # 같은 종류의 등록과 공개 판단이 겹치지 않게 종류를 잠근다.
        await self.listings.lock_definition(listing.item_definition_id)

        # 잠금 순서(매물 → 아이템 → 사용자 → 지갑)를 지키려고 다음 매물을 정산 전에 잠근다.
        next_listing = await self._lock_next_queued(listing.item_definition_id)

        if listing.has_bidder():
            await self._settle(listing, now)
        else:
            await self._fail(listing, now)

        # 현재 매물이 종료된 뒤 다음 매물을 공개한다. 실패하면 위 처리와 함께 rollback된다.
        if next_listing is not None:
            next_listing.start(now)
            await self.listings.save(next_listing)

        return True

    # 입찰자가 없는 매물을 유찰 처리하고 아이템 예약을 해제한다.
    # 입력: 잠금된 매물·처리 시각. 반환값 없음. commit은 호출자가 한다.
    async def _fail(self, listing: Listing, now: datetime) -> None:
        listing.mark_failed(now)
        await self.inventory.release(
            inventory_item_id=listing.inventory_item_id,
            owner_id=listing.seller_id,
            listing_id=listing.id,
            now=now,
        )
        await self.listings.save(listing)

    # [AUC-05] 낙찰 정산: 아이템 이전 → 사용자 잠금 → 재화 이전 → SOLD → 거래 기록 → 낙찰 제한 갱신.
    # 입력: 잠금된 매물·처리 시각. 반환값 없음.
    # 어느 단계든 실패하면 예외를 전달하고, 호출자가 전체 rollback한다.
    async def _settle(self, listing: Listing, now: datetime) -> None:
        seller_id = listing.seller_id
        buyer_id = listing.current_bidder_id
        price = listing.current_bid_amount

        # 거래 기록에 남길 아이템 이름을 조회한다. (잠금 없음)
        item = await self.inventory.get_summary(listing.inventory_item_id)

        # [아이템 잠금] 판매자 소유 확인 후 구매자에게 이전한다.
        await self.inventory.transfer_reserved(
            inventory_item_id=listing.inventory_item_id,
            from_user_id=seller_id,
            to_user_id=buyer_id,
            listing_id=listing.id,
            now=now,
        )

        # [사용자 잠금] 같은 사용자의 낙찰 제한 갱신이 겹치지 않게 ID 오름차순으로 잠근다.
        users = await self.users.get_for_update_many([seller_id, buyer_id])
        buyer = users.get(buyer_id)
        if buyer is None:
            raise NotFoundError("낙찰자를 찾을 수 없습니다.")

        # [지갑 잠금] 구매자 차감·판매자 지급. 잔액 부족 등은 예외로 전달된다.
        await self.wallets.settle_sale(
            buyer_id=buyer_id,
            seller_id=seller_id,
            price=price,
        )

        listing.mark_sold(now)
        sold = await self.listings.save(listing)

        # 체결 당시 이름을 스냅샷으로 남긴다. 찾지 못한 이름은 표시값으로 대신한다.
        names = await self.users.get_display_names([seller_id, buyer_id])
        trade = Trade.from_sold_listing(
            sold,
            item_name=item.name,
            seller_name=names.get(seller_id, UNKNOWN_NAME),
            buyer_name=names.get(buyer_id, UNKNOWN_NAME),
            now=now,
        )
        await self.trades.save(trade)

        # 이번 거래를 저장한 뒤 조회해야 이번 낙찰이 정확히 한 번 포함된다.
        win_times = await self.trades.find_win_times_between(
            buyer_id,
            since=now - WIN_LIMIT_WINDOW,
            until=now,
        )
        state = calculate_limit_after_win(win_times, buyer.blocked_until, now)
        await self.users.update_limit(
            buyer_id,
            state.purchase_count,
            state.blocked_until,
        )

    # 같은 종류에서 다음으로 공개할 가장 오래된 대기 매물을 잠금 조회한다.
    # 입력: 아이템 종류 ID. 반환: 잠금된 QUEUED 매물, 없으면 None.
    # 후보가 잠금 사이에 취소됐으면 다음 후보를 다시 찾는다.
    async def _lock_next_queued(self, item_definition_id: int) -> Listing | None:
        while True:
            candidate = await self.listings.next_queued(item_definition_id)
            if candidate is None:
                return None

            locked = await self.listings.get_for_update(candidate.id)
            if locked is not None and locked.status == ListingStatus.QUEUED:
                return locked

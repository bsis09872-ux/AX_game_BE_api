# Service: 사용자 요청을 완료하는 데 필요한 작업 순서를 조율한다.
# 매물 규칙은 Listing에, DB 작업은 Repository에, 다른 도메인 작업은 Gateway에 맡긴다.
# 변경 요청은 같은 세션에서 처리하고 마지막에 tx.commit으로 확정한다.
# 중간에 오류가 나면 commit하지 않고 올리며, get_db가 rollback한다.
# 잠금 순서: 매물 → 아이템 → 사용자 → 지갑.

from datetime import datetime

from auction.application.contract import (
    AuctionUserGateway,
    InventoryGateway,
    TransactionManager,
    WalletGateway,
)
from auction.domain.exceptions import BidBannedError
from auction.domain.listings.entities import Listing
from auction.domain.listings.repositories import ListingRepository
from auction.domain.trades.policies import get_limit_state
from shared.core.exceptions import BusinessRuleError, NotFoundError


class ListingService:
    def __init__(
        self,
        listings: ListingRepository,
        inventory: InventoryGateway,
        users: AuctionUserGateway,
        wallets: WalletGateway,
        tx: TransactionManager,
    ):
        self.listings = listings
        self.inventory = inventory
        self.users = users
        self.wallets = wallets
        self.tx = tx

    # 경매장 목록을 열면 현재 공개 중인 매물을 가져온다.
    async def get_listings(self, page: int) -> list[Listing]:
        return await self.listings.list_bidding(page)

    # 매물을 선택하면 상세 정보를 가져온다. 없으면 찾을 수 없다고 알린다.
    async def get_listing(self, listing_id: int) -> Listing:
        listing = await self.listings.get(listing_id)

        if listing is None:
            raise NotFoundError("매물을 불러올 수 없습니다.")

        return listing

    # [AUC-01] 아이템 종류 확인 → 매물 생성·공개 판단 → 저장 → 아이템 예약 → 확정.
    # 매물을 먼저 저장해 ID를 받고, 아이템 이력에 매물 ID를 남긴다.
    # 소유권·아이템 상태·재판매 제한은 reserve에서 인벤토리가 검사한다.
    # [TO DO] 같은 종류를 동시에 등록하면 둘 다 공개될 수 있으므로 종류별 잠금을 정한다. (진행 전)
    async def register(
        self,
        seller_id: int,
        inventory_item_id: int,
        start_price: int,
        now: datetime,
    ) -> Listing:
        item = await self.inventory.get_summary(inventory_item_id)

        listing = Listing.create(
            seller_id=seller_id,
            inventory_item_id=inventory_item_id,
            item_definition_id=item.item_definition_id,
            start_price=start_price,
            now=now,
        )
        if not await self.listings.exists_bidding(item.item_definition_id):
            listing.start(now)

        saved = await self.listings.save(listing)
        await self.inventory.reserve(inventory_item_id, seller_id, saved.id, now)
        await self.tx.commit()
        return saved

    # [AUC-04] 매물·사용자 잠금 → 제한 확인 → 입찰 검사 → 사용 가능 금액 확인 → 저장 → 확정.
    # 사용자를 잠가 같은 사용자의 동시 입찰이 묶인 금액을 함께 계산하지 않게 한다.
    # [TO DO] Wallet 계약이 정해지면 잔액 부족을 INSUFFICIENT_BALANCE로 맞춘다. (진행 전)
    async def bid(
        self,
        listing_id: int,
        bidder_id: int,
        amount: int,
        now: datetime,
    ) -> Listing:
        listing = await self._get_for_update(listing_id)

        users = await self.users.get_for_update_many([bidder_id])
        user = users.get(bidder_id)
        if user is None:
            raise NotFoundError("사용자를 찾을 수 없습니다.")

        limit = get_limit_state(win_times=[], blocked_until=user.blocked_until, now=now)
        if limit.is_blocked:
            raise BidBannedError()

        listing.place_bid(bidder_id, amount, now)

        # 다른 매물에 최고 입찰로 묶인 금액 + 이번 입찰액만큼 잔액이 있어야 한다.
        tied = await self.listings.sum_leading_bids(bidder_id)
        if not await self.wallets.has_balance(bidder_id, tied + amount):
            raise BusinessRuleError("사용 가능한 골드가 부족합니다.")

        saved = await self.listings.save(listing)
        await self.tx.commit()
        return saved

    # [AUC-11] 매물 잠금 → 취소(판매자·QUEUED 검사) → 저장 → 아이템 예약 해제 → 확정.
    async def cancel(
        self,
        listing_id: int,
        requester_id: int,
        now: datetime,
    ) -> Listing:
        listing = await self._get_for_update(listing_id)
        listing.cancel(requester_id, now)

        saved = await self.listings.save(listing)
        await self.inventory.release(
            saved.inventory_item_id, saved.seller_id, saved.id, now
        )
        await self.tx.commit()
        return saved

    # 변경할 매물을 잠금 조회한다. 없으면 찾을 수 없다고 알린다.
    async def _get_for_update(self, listing_id: int) -> Listing:
        listing = await self.listings.get_for_update(listing_id)

        if listing is None:
            raise NotFoundError("매물을 불러올 수 없습니다.")

        return listing

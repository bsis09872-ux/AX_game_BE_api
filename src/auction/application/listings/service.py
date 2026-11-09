# Service: 사용자 요청을 완료하는 데 필요한 작업 순서를 조율한다.
# 매물 규칙은 Listing에, DB 작업은 Repository에, 다른 도메인 작업은 Gateway에 맡긴다.
# 변경 요청은 같은 세션에서 처리하고 마지막에 transaction.commit으로 확정한다.
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
from auction.domain.listings.entities import Listing, ListingStatus
from auction.domain.listings.repositories import ListingRepository
from shared.core.exceptions import BusinessRuleError, NotFoundError, ForbiddenError

# 매물 조회·등록·입찰·취소를 조율한다.
# 관리자 기능도 이 클래스에 추가하며, 관리자 전용 메서드에서 권한을 검사한다.
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

    # 경매장 "목록"을 열면 현재 "공개 중인 매물"을 가져온다.
    async def get_listing_list(self, page: int) -> list[Listing]:
        return await self.listings.list_bidding(page)

    # "매물"을 선택하면 "상세 정보"를 가져온다. 없으면 찾을 수 없다고 알린다.
    async def get_listing_detail(self, listing_id: int) -> Listing:
        listing = await self.listings.get(listing_id)

        if listing is None:
            raise NotFoundError("매물을 불러올 수 없습니다.")

        return listing

    # 인증된 요청자 ID와 조회 조건을 받아 관리자 권한부터 확인한다.
    # 관리자이면 조건에 맞는 모든 상태의 매물을 페이지별로 반환한다.
    # 일반 사용자는 거절하며, 조회만 하므로 commit하지 않는다.
    async def get_admin_listings(
        self,
        requester_id: int,
        page: int,
        *,
        listing_id: int | None = None,
        item_definition_id: int | None = None,
        inventory_item_id: int | None = None,
        status: ListingStatus | None = None,
    ) -> list[Listing]:
        if not await self.users.is_admin(requester_id):
            raise ForbiddenError("관리자만 전체 매물을 조회할 수 있습니다.")

        if page < 1:
            raise BusinessRuleError("페이지 번호는 1 이상이어야 합니다.")

        return await self.listings.list_filtered(
            page=page,
            listing_id=listing_id,
            item_definition_id=item_definition_id,
            inventory_item_id=inventory_item_id,
            status=status,
        )

    # 아이템의 카탈로그 시작가로 매물을 생성한다.
    # 매물 저장으로 ID 확보 → 아이템 예약 이력에 ID 전달 → 전체 확정.
    # 예약 실패 시 예외를 전달하고 호출 측에서 전체 rollback한다.
    # [TO DO] 같은 아이템 종류의 동시 등록·공개를 직렬화한다.
    async def register(
        self,
        seller_id: int,
        inventory_item_id: int,
        now: datetime,
    ) -> Listing:
        item = await self.inventory.get_summary(inventory_item_id)

        listing = Listing.create(
            seller_id=seller_id,
            inventory_item_id=item.inventory_item_id,
            item_definition_id=item.item_definition_id,
            start_price=item.start_price,
            now=now,
        )

        if not await self.listings.exists_bidding(item.item_definition_id):
            listing.start(now)

        saved = await self.listings.save(listing)
        await self.inventory.reserve(
            inventory_item_id=item.inventory_item_id,
            owner_id=seller_id,
            listing_id=saved.id,
            now=now,
        )

        await self.tx.commit()
        return saved

    # [AUC-04] 매물·사용자 잠금 → 제한 확인 → 입찰 검사 → 지갑 자금 확인 → 저장 → 확정.
    # 사용자를 잠가 같은 사용자의 동시 입찰이 묶인 금액을 함께 계산하지 않게 한다.
    # 잔액 부족은 Wallet이 예외로 알리고, commit하지 않았으므로 get_db가 rollback한다.
    async def bid(
        self,
        listing_id: int,
        bidder_id: int,
        amount: int,
        now: datetime,
    ) -> Listing:
        listing = await self._get_for_update(listing_id)

        # 회원을 잠금 조회하고, 없거나 탈퇴한 회원은 거절한다.
        users = await self.users.get_for_update_many([bidder_id])
        user = users.get(bidder_id)
        if user is None or not user.is_active:
            raise NotFoundError("활성 사용자를 찾을 수 없습니다.")

        # 자동 제한과 관리자 제한이 반영된 최종 시각으로 입찰을 검사한다.
        # 종료 시각과 같으면 허용한다. 자동 제한 계산·저장에는 사용하지 않는다.
        if (
            user.effective_blocked_until is not None
            and now < user.effective_blocked_until
        ):
            raise BidBannedError()

        # place_bid가 최고 입찰 정보를 덮어쓰므로 변경 전 값을 먼저 보관한다.
        previous_bidder_id = listing.current_bidder_id
        previous_bid_amount = listing.current_bid_amount

        listing.place_bid(bidder_id, amount, now)

        # 예약 금액 계산과 지갑 잠금은 Wallet이 한다. 부족하면 예외가 그대로 올라간다.
        await self.wallets.check_bid_funds(
            bidder_id=bidder_id,
            amount=amount,
            current_bidder_id=previous_bidder_id,
            current_bid_amount=previous_bid_amount,
        )

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

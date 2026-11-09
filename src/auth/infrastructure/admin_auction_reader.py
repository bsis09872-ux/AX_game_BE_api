from auction.application.listings.service import ListingService
from auction.domain.listings.entities import Listing
from auth.application.admin_dto import AdminListing


class AdminAuctionReaderAdapter:
    def __init__(self, listings: ListingService):
        self.listings = listings

    @staticmethod
    def _view(listing: Listing) -> AdminListing:
        if listing.id is None:
            raise RuntimeError('저장된 경매 매물의 ID가 없습니다.')
        return AdminListing(
            id=listing.id, seller_id=listing.seller_id,
            inventory_item_id=listing.inventory_item_id,
            item_definition_id=listing.item_definition_id,
            status=listing.status.value, start_price=listing.start_price,
            current_bidder_id=listing.current_bidder_id,
            current_bid_amount=listing.current_bid_amount,
            created_at=listing.created_at, started_at=listing.started_at,
            ends_at=listing.ends_at, closed_at=listing.closed_at,
        )

    async def list_bidding(self, page: int) -> tuple[list[AdminListing], bool]:
        rows = await self.listings.get_listings(page)
        has_next = bool(rows) and bool(await self.listings.get_listings(page + 1))
        return [self._view(row) for row in rows], has_next

    async def get_listing(self, listing_id: int) -> AdminListing:
        return self._view(await self.listings.get_listing(listing_id))

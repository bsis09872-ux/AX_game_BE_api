from auction.application.listings.service import ListingService
from auction.application.trades.service import TradeService
from auction.domain.listings.entities import Listing, ListingStatus
from auction.domain.trades.entities import Trade
from auth.application.admin_dto import AdminListing, AdminListingStatus, AdminTrade
from shared.core.exceptions import NotFoundError


class AdminAuctionReaderAdapter:
    def __init__(self, listings: ListingService, trades: TradeService):
        self.listings = listings
        self.trades = trades

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
            admin_cancelled_by=listing.admin_cancelled_by,
        )

    async def list_listings(
        self, requester_id: int, page: int, *,
        listing_id: int | None = None,
        item_definition_id: int | None = None,
        inventory_item_id: int | None = None,
        status: AdminListingStatus | None = None,
    ) -> tuple[list[AdminListing], bool]:
        filters = dict(
            listing_id=listing_id,
            item_definition_id=item_definition_id,
            inventory_item_id=inventory_item_id,
            status=ListingStatus(status) if status else None,
        )
        rows = await self.listings.get_admin_listings(requester_id, page, **filters)
        # 마지막 페이지 여부도 같은 검색 조건으로 확인한다.
        has_next = bool(rows) and bool(
            await self.listings.get_admin_listings(requester_id, page + 1, **filters)
        )
        return [self._view(row) for row in rows], has_next

    async def get_listing(self, requester_id: int, listing_id: int) -> AdminListing:
        rows = await self.listings.get_admin_listings(requester_id, 1, listing_id=listing_id)
        if not rows:
            raise NotFoundError('매물을 찾을 수 없습니다.')
        return self._view(rows[0])

    @staticmethod
    def _trade_view(trade: Trade) -> AdminTrade:
        if trade.id is None:
            raise RuntimeError('저장된 거래 기록의 ID가 없습니다.')
        return AdminTrade(
            id=trade.id, listing_id=trade.listing_id,
            seller_id=trade.seller_id, buyer_id=trade.buyer_id,
            item_name_snapshot=trade.item_name_snapshot,
            seller_name_snapshot=trade.seller_name_snapshot,
            buyer_name_snapshot=trade.buyer_name_snapshot,
            price_snapshot=trade.price_snapshot, completed_at=trade.completed_at,
        )

    async def list_trades(
        self, requester_id: int, page: int, *,
        listing_id: int | None = None,
        buyer_id: int | None = None,
        seller_id: int | None = None,
    ) -> tuple[list[AdminTrade], bool]:
        filters = dict(listing_id=listing_id, buyer_id=buyer_id, seller_id=seller_id)
        rows = await self.trades.get_admin_trades(requester_id, page, **filters)
        has_next = bool(rows) and bool(
            await self.trades.get_admin_trades(requester_id, page + 1, **filters)
        )
        return [self._trade_view(row) for row in rows], has_next

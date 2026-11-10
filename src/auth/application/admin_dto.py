from dataclasses import dataclass
from datetime import datetime
from typing import Literal


AdminListingStatus = Literal['QUEUED', 'BIDDING', 'SOLD', 'FAILED', 'CANCELLED']


@dataclass(frozen=True)
class AdminListing:
    id: int
    seller_id: int
    inventory_item_id: int
    item_definition_id: int
    status: str
    start_price: int
    current_bidder_id: int | None
    current_bid_amount: int | None
    created_at: datetime
    started_at: datetime | None
    ends_at: datetime | None
    closed_at: datetime | None


@dataclass(frozen=True)
class AdminTrade:
    id: int
    listing_id: int
    seller_id: int
    buyer_id: int
    item_name_snapshot: str
    seller_name_snapshot: str
    buyer_name_snapshot: str
    price_snapshot: int
    completed_at: datetime

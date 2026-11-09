from dataclasses import dataclass
from datetime import datetime


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

from typing import Protocol

from auth.application.admin_dto import AdminListing, AdminListingStatus, AdminTrade


# TODO(지갑 담당): 관리자 전용 잔액과 지갑 원장 조회 계약이 제공되면 연결한다.


class AdminAuctionReader(Protocol):
    """관리자 화면에서 사용하는 경매 조회 계약. 상태 변경과 commit은 수행하지 않는다."""

    async def list_listings(
        self, requester_id: int, page: int, *,
        listing_id: int | None = None,
        item_definition_id: int | None = None,
        inventory_item_id: int | None = None,
        status: AdminListingStatus | None = None,
    ) -> tuple[list[AdminListing], bool]: ...

    async def get_listing(self, requester_id: int, listing_id: int) -> AdminListing: ...

    async def list_trades(
        self, requester_id: int, page: int, *,
        listing_id: int | None = None,
        buyer_id: int | None = None,
        seller_id: int | None = None,
    ) -> tuple[list[AdminTrade], bool]: ...

    # 관리자 강제 취소는 경매 도메인의 전용 서비스가 제공된 뒤 연결한다.
    # 판매자 취소와 관리자 강제 취소는 같은 기능으로 취급하지 않는다.

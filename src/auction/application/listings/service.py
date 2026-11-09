# Service: 사용자 요청을 완료하는 데 필요한 작업 순서를 조율한다.
# 매물 규칙은 Listing에, DB 작업은 Repository에 맡긴다.
# [TO DO] 외부 계약 확정 후 등록·입찰·취소에 필요한 의존성을 추가한다.

from datetime import datetime

from auction.domain.listings.entities import Listing
from auction.domain.listings.repositories import ListingRepository
from shared.core.exceptions import NotFoundError

class ListingService:
    def __init__(self, listings: ListingRepository):
        self.listings = listings

    # 경매장 목록을 열면 현재 공개 중인 매물을 가져온다.
    async def get_listings(self, page: int) -> list[Listing]:
        return await self.listings.list_bidding(page)

    # 매물을 선택하면 상세 정보를 가져온다. 없으면 찾을 수 없다고 알린다.
    async def get_listing(self, listing_id: int) -> Listing:
        listing = await self.listings.get(listing_id)

        if listing is None:
            raise NotFoundError("매물을 불러올 수 없습니다.")

        return listing

    # 판매자·아이템 ID, 시작가, 처리 시각을 받아 매물을 등록한다.
    # 구현 예정: 아이템 예약 → 매물 생성·공개 판단 → 저장.
    # 반환 예정: 저장된 Listing. 현재는 미구현임을 예외로 알린다.
    async def register(
        self,
        seller_id: int,
        inventory_item_id: int,
        start_price: int,
        now: datetime,
    ) -> Listing:
        # [TO DO] 시작가 입력 주체와 아이템 예약 계약을 확정한다.
        # [TO DO] inventory에서 아이템 종류 ID를 받고 예약을 요청한다.
        # [TO DO] Listing.create와 공개 여부 판단, 저장을 연결한다.
        # [TO DO] 아이템 예약과 매물 저장을 같은 트랜잭션으로 처리한다.
        raise NotImplementedError(
            "매물 등록은 아이템 예약·공개 조율·트랜잭션 연결 후 구현합니다."
        )

    # 입찰 요청을 받으면 사용자 제한과 잔액을 확인하고 매물에 입찰을 전달한다.
    async def bid(
        self,
        listing_id: int,
        bidder_id: int,
        amount: int,
        now: datetime,
    ) -> Listing:
        # [TO DO] 사용자·매물·지갑을 합의한 순서로 잠금 조회한다.
        # [TO DO] get_limit_state로 새 입찰 제한 여부를 확인한다.
        # [TO DO] 잔액 - 최고 입찰액 합계가 이번 입찰액 이상인지 확인한다.
        # [TO DO] Listing.place_bid 호출 후 저장하고 트랜잭션을 확정한다.
        raise NotImplementedError("사용자 제한·지갑·잠금 계약 연결이 필요합니다.")

    # 취소 요청을 받으면 매물을 취소하고 아이템 예약도 함께 해제한다.
    async def cancel(
        self,
        listing_id: int,
        requester_id: int,
        now: datetime,
    ) -> Listing:
        # [TO DO] 매물을 잠금 조회하고 없으면 NotFoundError를 발생시킨다.
        # [TO DO] Listing.cancel이 판매자와 QUEUED 상태를 검사하게 한다.
        # [TO DO] inventory 예약 해제와 매물 저장을 함께 확정한다.
        raise NotImplementedError("아이템 예약 해제·트랜잭션 연결이 필요합니다.")
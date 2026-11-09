# Adapter: Wallet의 예약 금액 조회 요청을 Auction Repository에 연결한다.
# Wallet 모델이나 테이블을 참조하지 않고 합계만 반환한다.

from auction.domain.listings.repositories import ListingRepository


class AuctionHeldAmountReader:
    # 같은 요청 세션을 사용하는 매물 Repository를 받는다.
    def __init__(self, listings: ListingRepository) -> None:
        self._listings = listings

    # 사용자가 최고 입찰자인 BIDDING 매물의 입찰액 합계를 반환한다.
    # 마감 후 정산 전 매물도 포함하며, 해당 매물이 없으면 0이다.
    # 추가 행 잠금이나 commit은 하지 않는다.
    async def held_amount(self, user_id: int) -> int:
        return await self._listings.sum_leading_bids(user_id)
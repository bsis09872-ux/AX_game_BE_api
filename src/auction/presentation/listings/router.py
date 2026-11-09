# 매물 HTTP 요청을 검증하고 application 서비스를 호출한다. 업무 규칙과 SQL은 넣지 않는다.
# 사용자 ID는 CurrentUserId로만 받는다. 본문의 사용자 ID를 신뢰하지 않는다.
# 서비스는 dependencies의 별칭으로 주입받으며 ORM 모델은 응답으로 내보내지 않는다.
# [TO DO] 목록이 비어도 성공 응답으로 반환하고 팀 공통 목록 형식을 따른다.
# 입찰 제한 오류는 전역 핸들러에 전달한다. 여기서 별도 403이나 오류 로깅을 추가하지 않는다.

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Query, status

from auction.presentation.dependencies import CurrentUserId, ListingServiceDep
from auction.presentation.listings.schemas import (
    BidRequest,
    ListingCreateRequest,
    ListingPageResponse,
    ListingResponse,
)


router = APIRouter(prefix="/listings", tags=["listings"])


# [AUC-02] 매물 목록 조회: BIDDING만, 공개 시각 최신순
@router.get("", response_model=ListingPageResponse, summary="매물 목록 조회")
async def get_listings(
    service: ListingServiceDep,
    page: Annotated[int, Query(ge=1)] = 1,
) -> ListingPageResponse:
    listings = await service.get_listings(page)
    return ListingPageResponse(
        items=[ListingResponse.from_listing(listing) for listing in listings],
        page=page,
    )


# [AUC-03] 매물 상세 조회
@router.get("/{listing_id}", response_model=ListingResponse, summary="매물 상세 조회")
async def get_listing(
    listing_id: int,
    service: ListingServiceDep,
) -> ListingResponse:
    listing = await service.get_listing(listing_id)
    return ListingResponse.from_listing(listing)

# [AUC-01] 매물 등록: 같은 종류가 공개 중이면 QUEUED, 아니면 바로 BIDDING
@router.post(
    "",
    response_model=ListingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="매물 등록",
)
async def register_listing(
    body: ListingCreateRequest,
    user_id: CurrentUserId,
    service: ListingServiceDep,
) -> ListingResponse:
    listing = await service.register(
        seller_id=user_id,
        inventory_item_id=body.inventory_item_id,
        start_price=body.start_price,
        now=datetime.now(timezone.utc),
    )
    return ListingResponse.from_listing(listing)


# [AUC-04] 입찰
@router.post("/{listing_id}/bids", response_model=ListingResponse, summary="입찰")
async def place_bid(
    listing_id: int,
    body: BidRequest,
    user_id: CurrentUserId,
    service: ListingServiceDep,
) -> ListingResponse:
    listing = await service.bid(
        listing_id=listing_id,
        bidder_id=user_id,
        amount=body.amount,
        now=datetime.now(timezone.utc),
    )
    return ListingResponse.from_listing(listing)


# [AUC-11] 매물 등록 취소: 실제 삭제가 아니라 CANCELLED로 바꾼다.
@router.delete(
    "/{listing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="매물 등록 취소",
)
async def cancel_listing(
    listing_id: int,
    user_id: CurrentUserId,
    service: ListingServiceDep,
) -> None:
    await service.cancel(
        listing_id=listing_id,
        requester_id=user_id,
        now=datetime.now(timezone.utc),
    )

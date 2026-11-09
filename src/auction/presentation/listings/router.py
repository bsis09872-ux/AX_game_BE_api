# 매물 HTTP 요청을 검증하고 application 서비스를 호출한다. 업무 규칙과 SQL은 넣지 않는다.
# [TO DO] 등록·입찰·등록 취소 엔드포인트를 연결한다. (진행 전)
# 사용자 ID는 CurrentUserId로만 받는다. 본문의 사용자 ID를 신뢰하지 않는다.
# 서비스는 dependencies의 별칭으로 주입받으며 ORM 모델은 응답으로 내보내지 않는다.

# [TO DO] 목록이 비어도 성공 응답으로 반환하고 팀 공통 목록 형식을 따른다.
# [TO DO] 취소 URI·HTTP 메서드와 공통 응답 형식을 합의한다.
# [TO DO] 앱 담당자에게 라우터 등록을 요청한다. 현재 main의 공통 접두사는 /v1이다.
# 입찰 제한 오류는 전역 핸들러에 전달한다. 여기서 별도 403이나 오류 로깅을 추가하지 않는다.

from typing import Annotated

from fastapi import APIRouter, Query

from auction.presentation.dependencies import ListingServiceDep
from auction.presentation.listings.schemas import ListingPageResponse, ListingResponse

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

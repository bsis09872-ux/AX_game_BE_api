# 매물 요청과 응답의 형태를 정의한다. 입찰 가능 여부는 domain이 판단한다.
# [TO DO] 등록 요청의 inventory_item_id와 시작가 입력 정책을 팀과 확정한다.
# [TO DO] 목록 page 검증과 응답 스키마를 현재 Repository 계약에 맞춘다.
# [TO DO] 검색·필터는 Repository에 아직 없으므로 지원한다고 표시하지 않는다.
# [TO DO] 목록·상세 응답의 ID·상태·가격·종료 시각과 외부 이름 조회 계약을 정한다.
# [TO DO] 입찰자 ID 공개 여부와 취소 응답 형식을 합의한다.
# 시간은 UTC ISO 8601로 반환한다. KST 표시는 화면 담당자가 변환한다.

from datetime import datetime

from pydantic import BaseModel, Field

from auction.domain.listings.entities import Listing

# [AUC-01] 매물 등록 요청: 판매자 ID는 토큰에서 받으므로 본문에 넣지 않는다.
# [TO DO] 시작가 입력 주체(D-4)가 정해지면 start_price 유지 여부를 정한다. (진행 전)
class ListingCreateRequest(BaseModel):
    inventory_item_id: int = Field(gt=0)

# [AUC-04] 입찰 요청: 시작가·최고가 비교는 엔티티가 한다.
class BidRequest(BaseModel):
    amount: int = Field(gt=0)


# [관리자] 강제 취소 요청: 관리자 ID는 토큰에서 받으므로 본문에 넣지 않는다.
# 사유는 내부 기록용이며 1~200자. 공백만 있는 사유는 엔티티가 400으로 거절한다.
class AdminCancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=200)


# [관리자] 강제 취소 응답: 안내 메시지만 반환한다.
# 사유·관리자 ID 등 내부 기록은 응답에 싣지 않는다.
class AdminCancelResponse(BaseModel):
    message: str = "관리자에 의해 경매가 취소되었습니다."


# 매물 응답: 여기에 적은 필드만 밖으로 나간다. 최고 입찰자 ID는 공개 여부가 정해지기 전까지 싣지 않는다.
class ListingResponse(BaseModel):
    id: int
    inventory_item_id: int
    item_definition_id: int
    seller_id: int
    start_price: int
    current_bid_amount: int | None
    status: str
    started_at: datetime | None
    ends_at: datetime | None

    # 도메인 엔티티를 응답 모델로 변환한다.
    @classmethod
    def from_listing(cls, listing: Listing) -> "ListingResponse":
        return cls(
            id=listing.id,
            inventory_item_id=listing.inventory_item_id,
            item_definition_id=listing.item_definition_id,
            seller_id=listing.seller_id,
            start_price=listing.start_price,
            current_bid_amount=listing.current_bid_amount,
            status=listing.status.value,
            started_at=listing.started_at,
            ends_at=listing.ends_at,
        )


# 매물 목록 응답
# [TO DO] 팀 공통 목록 형식(size·total 포함 여부)을 확정한다. (진행 전)
class ListingPageResponse(BaseModel):
    items: list[ListingResponse]
    page: int

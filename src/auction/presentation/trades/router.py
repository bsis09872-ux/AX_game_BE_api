# 내 낙찰·판매 내역과 입찰 제한 상태 요청을 application으로 전달한다.
# 사용자 ID는 CurrentUserId로만 받는다. 다른 사용자의 상태를 임의 조회하지 않는다.
# 제한 중에도 조회는 허용한다. 새 입찰 거절은 매물 입찰 흐름에서 처리한다.
# [TO DO] 내역 조회와 제한 상태 조회 URI를 팀과 합의하고 공통 응답을 적용한다.

from datetime import datetime, timezone

from fastapi import APIRouter

from auction.presentation.dependencies import CurrentUserId, TradeServiceDep
from auction.presentation.params import OptionalIdQuery, PageQuery
from auction.presentation.trades.schemas import (
    BidLimitResponse,
    TradePageResponse,
    TradeResponse,
)

router = APIRouter(prefix="/trades", tags=["trades"])

# 인증된 요청자 ID와 필터를 받아 관리자 거래 조회를 요청한다.
# 관리자 권한은 서비스에서 검사하고, 결과를 거래 목록 응답으로 변환한다.
@router.get(
    "/management",
    response_model=TradePageResponse,
    summary="관리자 거래 내역 조회",
    tags=["auction-management"],
)
async def get_admin_trades(
    user_id: CurrentUserId,
    service: TradeServiceDep,
    page: PageQuery = 1,
    listing_id: OptionalIdQuery = None,
    buyer_id: OptionalIdQuery = None,
    seller_id: OptionalIdQuery = None,
) -> TradePageResponse:
    trades = await service.get_admin_trades(
        requester_id=user_id,
        page=page,
        listing_id=listing_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
    )
    return TradePageResponse(
        items=[TradeResponse.from_trade(trade) for trade in trades],
        page=page,
    )

# [AUC-07] 내 낙찰 내역: 체결 시각 최신순
@router.get("/me/won", response_model=TradePageResponse, summary="내 낙찰 내역 조회")
async def get_my_purchases(
    user_id: CurrentUserId,
    service: TradeServiceDep,
    page: PageQuery = 1,
) -> TradePageResponse:
    trades = await service.get_my_purchases(user_id, page)
    return TradePageResponse(
        items=[TradeResponse.from_trade(trade) for trade in trades],
        page=page,
    )


# [AUC-10] 내 판매 내역: 체결 시각 최신순
@router.get("/me/sold", response_model=TradePageResponse, summary="내 판매 내역 조회")
async def get_my_sales(
    user_id: CurrentUserId,
    service: TradeServiceDep,
    page: PageQuery = 1,
) -> TradePageResponse:
    trades = await service.get_my_sales(user_id, page)
    return TradePageResponse(
        items=[TradeResponse.from_trade(trade) for trade in trades],
        page=page,
    )


# [AUC-08] 내 입찰 제한 상태
@router.get("/me/bid-limit", response_model=BidLimitResponse, summary="내 입찰 제한 상태 조회")
async def get_my_bid_limit(
    user_id: CurrentUserId,
    service: TradeServiceDep,
) -> BidLimitResponse:
    state = await service.get_bid_limit_status(user_id, datetime.now(timezone.utc))
    return BidLimitResponse.from_state(state)

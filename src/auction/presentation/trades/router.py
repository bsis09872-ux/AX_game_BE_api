# 내 낙찰·판매 내역과 입찰 제한 상태 요청을 application으로 전달한다.
# [TO DO] 인증 사용자 ID를 서비스에 전달한다. 다른 사용자의 상태를 임의 조회하지 않는다.
# [TO DO] 내역 조회와 제한 상태 조회 URI를 팀과 합의하고 공통 응답을 적용한다.
# [TO DO] 제한 중에도 조회를 허용한다. 새 입찰 거절은 매물 입찰 흐름에서 처리한다.
# [TO DO] 인증·서비스 의존성을 연결하고 앱 담당자에게 라우터 등록을 요청한다.

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Query

from auction.presentation.dependencies import CurrentUserId, TradeServiceDep
from auction.presentation.trades.schemas import (
    BidLimitResponse,
    TradePageResponse,
    TradeResponse,
)

router = APIRouter(prefix="/trades", tags=["trades"])

Page = Annotated[int, Query(ge=1)]


# [AUC-07] 내 낙찰 내역: 체결 시각 최신순
@router.get("/me/won", response_model=TradePageResponse, summary="내 낙찰 내역 조회")
async def get_my_purchases(
    user_id: CurrentUserId,
    service: TradeServiceDep,
    page: Page = 1,
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
    page: Page = 1,
) -> TradePageResponse:
    trades = await service.get_my_sales(user_id, page)
    return TradePageResponse(
        items=[TradeResponse.from_trade(trade) for trade in trades],
        page=page,
    )


# [AUC-08] 내 입찰 제한 상태
# [TO DO] users의 낙찰 횟수 조회가 제공되기 전까지는 500을 반환한다. (진행 전)
@router.get("/me/bid-limit", response_model=BidLimitResponse, summary="내 입찰 제한 상태 조회")
async def get_my_bid_limit(
    user_id: CurrentUserId,
    service: TradeServiceDep,
) -> BidLimitResponse:
    state = await service.get_bid_limit_status(user_id, datetime.now(timezone.utc))
    return BidLimitResponse.from_state(state)

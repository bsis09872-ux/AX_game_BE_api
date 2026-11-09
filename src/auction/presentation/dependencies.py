# 의존성 자리 표시자: 실제 구현은 auction/wiring.py가 app.dependency_overrides로 연결한다.
# presentation은 서비스 타입만 알고 DB·Repository·인증 구현을 모른다.
# 라우터는 아래 별칭(~Dep, CurrentUserId)으로 주입받는다.

from typing import Annotated

from fastapi import Depends

from auction.application.listings.service import ListingService
from auction.application.trades.service import TradeService


def provide_listing_service() -> ListingService:
    raise NotImplementedError("ListingService 의존성이 주입되지 않았습니다.")


def provide_trade_service() -> TradeService:
    raise NotImplementedError("TradeService 의존성이 주입되지 않았습니다.")


async def provide_current_user_id() -> int:
    raise NotImplementedError("현재 사용자 의존성이 주입되지 않았습니다.")


ListingServiceDep = Annotated[ListingService, Depends(provide_listing_service)]
TradeServiceDep = Annotated[TradeService, Depends(provide_trade_service)]
CurrentUserId = Annotated[int, Depends(provide_current_user_id)]

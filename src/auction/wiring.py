# 경매의 부품 조립: 같은 세션으로 Repository·Adapter를 만들어 서비스에 주입한다.
# 다른 도메인은 그 도메인의 wiring으로만 가져온다. (infrastructure를 직접 import하지 않는다)
# 세션은 호출자가 만들고 닫는다. 같은 세션이면 한 트랜잭션으로 묶인다.
# 업무 규칙을 두지 않는다.
#
# [TO DO] page_size를 외부 설정에서 받는다. (진행 전)

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from auction.presentation import dependencies as deps
from database import get_db


from auction.application.auction_service import AuctionService
from auction.application.listings.service import ListingService
from auction.application.trades.service import TradeService

from auction.infrastructure.adapters.inventory_gateway import InventoryGatewayAdapter
from auction.infrastructure.adapters.transaction import SqlAlchemyTransactionManager
from auction.infrastructure.adapters.user_gateway import AuctionUserGatewayAdapter
from auction.infrastructure.adapters.wallet_gateway import WalletGatewayAdapter

from auction.infrastructure.listings.repositories import SqlAlchemyListingRepository
from auction.infrastructure.trades.repositories import SqlAlchemyTradeRepository

from inventory.wiring import build_inventory_service
from users.wiring import build_user_service

PAGE_SIZE = 20


def build_user_gateway(session: AsyncSession) -> AuctionUserGatewayAdapter:
    return AuctionUserGatewayAdapter(build_user_service(session))


def build_inventory_gateway(session: AsyncSession) -> InventoryGatewayAdapter:
    return InventoryGatewayAdapter(build_inventory_service(session))

# 매물 조회·등록·입찰·취소
def build_listing_service(session: AsyncSession) -> ListingService:
    return ListingService(
        listings=SqlAlchemyListingRepository(session, page_size=PAGE_SIZE),
        inventory=build_inventory_gateway(session),
        users=build_user_gateway(session),
        wallets=WalletGatewayAdapter(),
        tx=SqlAlchemyTransactionManager(session),
    )



# 거래 기록·제한 조회
def build_trade_service(session: AsyncSession) -> TradeService:
    return TradeService(
        trades=SqlAlchemyTradeRepository(session, page_size=PAGE_SIZE),
        user_limit_reader=build_user_gateway(session),
    )


# 마감 정산 (스케줄러용)
def build_auction_service(session: AsyncSession) -> AuctionService:
    return AuctionService(
        listings=SqlAlchemyListingRepository(session, page_size=PAGE_SIZE),
        trades=SqlAlchemyTradeRepository(session, page_size=PAGE_SIZE),
        users=build_user_gateway(session),
        wallets=WalletGatewayAdapter(),
        inventory=build_inventory_gateway(session),
        tx=SqlAlchemyTransactionManager(session),
    )



# ===== FastAPI 의존성 연결 =====
# 앱 시작 시 presentation의 자리 표시자를 실제 구현으로 바꾼다.
# current_user_id는 main.py가 auth의 의존성을 넘겨 준다. (auth를 직접 import하지 않는다)

SessionDep = Annotated[AsyncSession, Depends(get_db)]


def _listing_service(session: SessionDep) -> ListingService:
    return build_listing_service(session)


def _trade_service(session: SessionDep) -> TradeService:
    return build_trade_service(session)


def wire_auction_dependencies(
    app: FastAPI,
    current_user_id: Callable[..., Awaitable[int]],
) -> None:
    app.dependency_overrides.update({
        deps.provide_listing_service: _listing_service,
        deps.provide_trade_service: _trade_service,
        deps.provide_current_user_id: current_user_id,
    })

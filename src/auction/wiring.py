# 경매의 부품 조립: 같은 세션으로 Repository·Adapter를 만들어 서비스에 주입한다.
# 다른 도메인은 그 도메인의 wiring으로만 가져온다. (infrastructure를 직접 import하지 않는다)
# 세션은 호출자가 만들고 닫는다. 같은 세션이면 한 트랜잭션으로 묶인다.
# 업무 규칙을 두지 않는다.
#
# [TO DO] page_size를 외부 설정에서 받는다. (진행 전)

from sqlalchemy.ext.asyncio import AsyncSession

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


# 매물 조회
def build_listing_service(session: AsyncSession) -> ListingService:
    return ListingService(
        listings=SqlAlchemyListingRepository(session, page_size=PAGE_SIZE),
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

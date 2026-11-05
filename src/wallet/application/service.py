"""지갑·거래 조회 서비스 (WALL-01, 04, 05)

시그니처는 service_interface.md를 따른다. 조회 전용이라 commit하지 않는다.
TODO: listings·trades·users 모델이 생기면 쿼리 구현
"""
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from shared.core.schemas import PageParams, PageResponse
from wallet.presentation.schemas import TradeDetailResponse, TradeListItem, WalletResponse


async def get_my_wallet(session: AsyncSession, *, user_id: int) -> WalletResponse:
    raise NotImplementedError


async def list_my_trades(
    session: AsyncSession,
    *,
    user_id: int,
    role: Literal["buy", "sell", "all"],
    page: PageParams,
) -> PageResponse[TradeListItem]:
    raise NotImplementedError


async def get_trade_detail(
    session: AsyncSession, *, user_id: int, trade_id: int
) -> TradeDetailResponse:
    raise NotImplementedError

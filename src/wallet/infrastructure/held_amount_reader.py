"""HeldAmountReader 구현 (임시): listings 테이블을 직접 읽어 예약 금액을 계산한다.

application/contracts.py의 HeldAmountReader 모양을 맞춘다 (계약 파일은 import하지 않는다).

TODO: auction이 같은 계산(ListingRepository.sum_leading_bids)을 서비스·계약으로 공개하면
      그 기능을 호출하는 어댑터로 바꾸고, external_tables.py의 listings 참조를 지운다.
      지금은 auction의 컬럼 이름·상태 값("BIDDING")이 바뀌면 조용히 깨질 수 있다.
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from wallet.infrastructure.external_tables import listings


class ListingsHeldAmountReader:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def held_amount(self, user_id: int) -> int:
        statement = select(func.coalesce(func.sum(listings.c.current_bid_amount), 0)).where(
            listings.c.current_bidder_id == user_id,
            listings.c.status == "BIDDING",  # 마감이 지나도 정산 전이면 BIDDING이라 포함된다
        )
        return int(await self._session.scalar(statement))

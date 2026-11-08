# [경매 주요 처리 기능] 마감된 매물의 정산·거래 생성·낙찰 제한 갱신·다음 매물 공개를 조율한다.
# 스케줄러는 이 서비스를 호출하며 이 파일에서 타이머나 SQL을 실행하지 않는다.
# [도메인 계층 역할] 매물 규칙은 Listing, 거래 기록은 Trade, 제한 계산은 policies에 맡긴다.
#
# 확정 정책: 최근 30분 내 3회 낙찰 시 15분간 새 입찰 제한.
# 제한 중에도 기존 입찰의 정산은 허용하고, 제한 종료 시각은 연장하지 않는다.
#
# 다른 도메인에 요청하는 기능(users·wallet·inventory)과 트랜잭션·잠금 순서 합의는 contract.py 상단 TODO를 따른다.
#
# [TO DO][제공 → 스케줄러 담당] 정산·다음 매물 공개 구현과 통합 검증 후 연결한다.
# 현재 close_expired는 미완성이므로 주기 실행에 등록하지 않는다.


import logging
from datetime import datetime

from auction.application.contract import (
    AuctionUserGateway,
    InventoryGateway,
    TransactionManager,
    WalletGateway,
)
from auction.domain.listings.entities import Listing, ListingStatus
from auction.domain.listings.repositories import ListingRepository

from auction.domain.trades.repositories import TradeRepository

logger = logging.getLogger(__name__)


class AuctionService:
    def __init__(
        self,
        listings: ListingRepository,
        trades: TradeRepository,
        users: AuctionUserGateway,
        wallets: WalletGateway,
        inventory: InventoryGateway,
        tx: TransactionManager,
    ):
        self.listings = listings
        self.trades = trades
        self.users = users
        self.wallets = wallets
        self.inventory = inventory
        self.tx = tx

    # [제공 → 스케줄러] 마감 시각이 지난 BIDDING 매물을 찾아 하나씩 종료한다.
    # 매물 1건 = 트랜잭션 1개. 한 건이 실패해도 이미 끝난 다른 매물의 정산은 유지된다.
    # 반환값: 이번 호출에서 실제로 종료한 매물 수.
    async def close_expired(self, now: datetime) -> int:
        # 후보 조회: 잠금 없이 가볍게 조회한다. 실제 처리는 _close_one에서 잠금 재조회 후 한다.
        candidates = await self.listings.list_expired_bidding(now)
        closed = 0

        for candidate in candidates:
            try:
                if await self._close_one(candidate.id, now):
                    await self.tx.commit()
                    closed += 1
                else:
                    # 건너뛴 매물: 바뀐 내용이 없으므로 rollback으로 잠금만 해제한다.
                    await self.tx.rollback()
            except NotImplementedError:
                # 미완성 기능이 호출되면 현재 매물의 변경을 되돌린다.
                # 오류를 호출자에게 전달하고 이번 마감 작업을 중단한다.
                await self.tx.rollback()
                raise

            except Exception:
                # 현재 매물의 변경을 되돌리고 실패 원인을 기록한다.
                # [TO DO] 낙찰자 탈퇴·비활성 등 업무 오류의 유찰 조건을 구분한다.
                # [TO DO] 아이템 누락·상태 불일치는 유찰로 덮지 않고 별도로 처리한다.
                # [TO DO] 재시도할 오류와 수동 확인이 필요한 오류를 구분한다.
                await self.tx.rollback()
                logger.exception(
                    "매물 마감 처리 실패: listing_id=%s",
                    candidate.id,
                )

        return closed

    # 매물 1건 종료: 잠금 재조회 → 입찰자 유무에 따라 낙찰/유찰 → 같은 종류의 다음 매물 공개.
    # 반환값: 종료했으면 True, 건너뛰었으면 False.
    async def _close_one(self, listing_id: int, now: datetime) -> bool:
        listing = await self.listings.get_for_update(listing_id)

        # 조회와 잠금 사이에 다른 작업이 먼저 종료했거나, 아직 마감 전이면 건너뛴다.
        if listing is None:
            return False
        if listing.status != ListingStatus.BIDDING or not listing.is_expired(now):
            return False

        # 입찰자 있음 → 낙찰 정산(_settle), 없음 → 유찰(_fail)
        # [TO DO] _settle·_open_next의 실제 처리는 다음 PR에서 구현한다.
        if listing.has_bidder():
            await self._settle(listing, now)
        else:
            await self._fail(listing, now)

        await self._open_next(listing.item_definition_id, now)
        return True

    # 매물과 처리 시각을 받아 유찰 상태로 바꾸고 아이템 예약을 해제한다.
    # 현재 호출 조건은 입찰자 없음이다. 업무 오류별 유찰 조건은 추후 구현한다.
    # 반환값 없음. 저장만 요청하고 commit은 호출자가 담당한다.
    async def _fail(self, listing: Listing, now: datetime) -> None:
        listing.mark_failed(now)
        await self.inventory.release(
            inventory_item_id=listing.inventory_item_id,
            owner_id=listing.seller_id,
            listing_id=listing.id,
            now=now,
        )
        await self.listings.save(listing)

    # 마감된 매물과 처리 시각을 받아 낙찰 정산을 수행할 자리다.
    # [TO DO] 재화·아이템 이전, 거래 기록 생성, 낙찰 제한 갱신을 연결한다.
    # 반환값 없음. 현재는 미구현 예외를 발생시킨다.
    async def _settle(self, listing: Listing, now: datetime) -> None:
        raise NotImplementedError(
            "낙찰 정산은 외부 도메인 연동 후 구현합니다."
        )

    # 아이템 종류 ID와 처리 시각을 받아 다음 대기 매물을 공개할 자리다.
    # [TO DO] 같은 종류의 공개 경쟁을 제어하고 대기 매물 조회·시작·저장을 연결한다.
    # 반환값 없음. 현재는 미구현 예외를 발생시킨다.
    async def _open_next(
        self,
        item_definition_id: int,
        now: datetime,
    ) -> None:
        raise NotImplementedError(
            "다음 매물 공개는 동시성 제어와 저장 흐름을 연결한 뒤 구현합니다."
        )

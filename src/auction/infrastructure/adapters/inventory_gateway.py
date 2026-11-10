# Inventory Adapter: 경매의 InventoryGateway 계약을 인벤토리 서비스에 연결한다.
# 인벤토리가 경매에 공개한 메서드만 호출하고 모델·테이블을 직접 읽지 않는다.
# 소유권·상태·재판매 제한 검사는 인벤토리 도메인이 한다.
# commit·rollback은 트랜잭션 담당자가 한다. 인벤토리 메서드도 flush까지만 한다.
# 인벤토리 오류는 공통 오류를 상속하므로 그대로 올린다.
# 단, 예약 해제(release)의 아이템 누락·상태·소유권 불일치는 내부 데이터 불일치로 보고
# 경매의 InventoryMismatchError(500)로 변환한다.
#
# [TO DO] 거래 기록 ID(trade_id)를 아이템 이력에 남길지 정산 순서와 함께 정한다. (진행 전)

import logging
from datetime import datetime

from auction.application.contract import InventoryGateway
from auction.application.dto import ItemSummary
from auction.domain.exceptions import InventoryMismatchError
from inventory.application.dto import ItemInfo
from inventory.application.service import InventoryService
from inventory.domain.exceptions import (
    InvalidStateError,
    ItemNotFoundError,
    NotOwnerError,
)

logger = logging.getLogger(__name__)

# 인벤토리 아이템 정보를 경매용 요약으로 바꾼다.
def _to_item_summary(info: ItemInfo) -> ItemSummary:
    return ItemSummary(
        inventory_item_id=info.id,
        item_definition_id=info.definition.id,
        name=info.definition.name,
        start_price=info.definition.start_price,
    )

class InventoryGatewayAdapter(InventoryGateway):

    def __init__(self, inventory_service: InventoryService) -> None:
        self._inventory_service = inventory_service

    # 판매 예약 (OWNED → LISTED)
    async def reserve(
        self,
        inventory_item_id: int,
        owner_id: int,
        listing_id: int | None,
        now: datetime,
    ) -> ItemSummary:
        info = await self._inventory_service.reserve_for_listing(
            inventory_item_id,
            by_owner_id=owner_id,
            now=now,
            listing_id=listing_id,
        )
        return _to_item_summary(info)

    # 예약 해제 (LISTED → OWNED): 판매자 취소·관리자 취소·유찰
    # 입력: 아이템 ID·소유자(판매자) ID·매물 ID·처리 시각. 반환값 없음.
    # 아이템 누락·상태 불일치·소유권 불일치는 사용자 오류가 아닌 내부 데이터 불일치다.
    # 원래 예외 유형과 ID를 로그로 남기고 경매 연동 예외(500)로 바꿔 올린다. rollback은 호출 측이 한다.
    async def release(
        self,
        inventory_item_id: int,
        owner_id: int,
        listing_id: int,
        now: datetime,
    ) -> None:
        try:
            await self._inventory_service.release_from_listing(
                inventory_item_id,
                by_owner_id=owner_id,
                now=now,
                listing_id=listing_id,
            )
        except (ItemNotFoundError, InvalidStateError, NotOwnerError) as exc:
            logger.error(
                "inventory_mismatch action=release error=%s "
                "listing_id=%s inventory_item_id=%s owner_id=%s",
                type(exc).__name__,
                listing_id,
                inventory_item_id,
                owner_id,
            )
            raise InventoryMismatchError() from exc

    # 소유권 이전 (LISTED → 구매자 OWNED): 낙찰 정산
    # from_owner_id를 넘겨 현재 소유자가 판매자인지 인벤토리가 확인하게 한다.
    async def transfer_reserved(
        self,
        inventory_item_id: int,
        from_user_id: int,
        to_user_id: int,
        listing_id: int,
        now: datetime,
    ) -> None:
        await self._inventory_service.transfer_to(
            inventory_item_id,
            new_owner_id=to_user_id,
            now=now,
            listing_id=listing_id,
            from_owner_id=from_user_id,
        )

    # 거래 기록용 아이템 정보 조회
    async def get_summary(
        self,
        inventory_item_id: int,
    ) -> ItemSummary:
        info = await self._inventory_service.get_item(inventory_item_id)
        return _to_item_summary(info)

# Contract: 경매가 외부에 요청하는 기능의 입력값과 반환값을 정의한다.
# Protocol은 계약만 선언하며 실제 조회·저장·잠금은 구현체가 담당한다.
# 외부 데이터는 dto.py의 형태로 전달받고 다른 도메인의 ORM에 의존하지 않는다.
# 구현체는 flush까지만 하며, commit은 호출하는 서비스가 한다.
#
# 합의한 잠금 순서: 매물 → 아이템 종류 → 다음 대기 매물 → 아이템 → 사용자 → 지갑.
# 여러 사용자를 잠글 때는 사용자 ID 오름차순으로 처리한다.
# 구현체는 wiring.py에서 같은 세션으로 조립하므로 Gateway와 Repository가 한 트랜잭션을 공유한다.
# 사용자 조회 결과의 낙찰 횟수는 저장값이며, 유효 횟수는 경매 정책으로 계산한다.

from datetime import datetime
from typing import Protocol

from auction.application.dto import AuctionUserState, ItemSummary

# 경매에서 필요한 사용자 조회·제한 상태 저장 기능의 계약이다.
class AuctionUserGateway(Protocol):
    # 사용자 ID로 제한 상태를 조회한다.
    # 반환: 사용자 상태 DTO. 사용자가 없으면 None.
    async def get_state(
        self,
        user_id: int,
    ) -> AuctionUserState | None:
        ...

    # 여러 사용자 ID를 받아 사용자 ID 오름차순으로 잠금 조회한다.
    # 반환: 사용자 ID를 키로 하고 상태 DTO를 값으로 하는 딕셔너리.
    # 없는 사용자는 결과에 포함하지 않으며, 없을 때의 처리는 호출하는 서비스가 정한다.
    async def get_for_update_many(
        self,
        user_ids: list[int],
    ) -> dict[int, AuctionUserState]:
        ...

    # 사용자 ID와 계산된 낙찰 횟수·제한 종료 시각을 받아 저장 요청한다.
    # 반환값 없음.
    async def update_limit(
        self,
        user_id: int,
        purchase_count: int,
        blocked_until: datetime | None,
    ) -> None:
        ...

    # 사용자 ID 목록으로 거래 기록에 남길 이름을 조회한다.
    # 반환: 사용자 ID와 이름을 연결한 딕셔너리.
    async def get_display_names(
        self,
        user_ids: list[int],
    ) -> dict[int, str]:
        ...

    # 인증된 요청자의 ID로 관리자 기능 사용 가능 여부를 조회한다.
    # 없는 회원·일반 회원·탈퇴 또는 로그인 정지 회원은 False를 반환한다.
    # 조회 중 발생한 오류는 숨기지 않고 전달한다.
    async def is_admin(
        self,
        user_id: int,
    ) -> bool:
        ...


# 입찰 가능 금액 확인과 낙찰 재화 이전을 Wallet에 요청한다.
# 실패는 예외로 전달받고, commit·rollback은 Auction에서 조율한다.
class WalletGateway(Protocol):
    # 입찰자·입찰액과 변경 전 최고 입찰 정보를 받아 자금 검사를 요청한다.
    # Wallet이 지갑을 잠그고 예약 금액을 조회한다. 부족하면 예외가 발생한다.
    # 정상 종료하면 검사 통과이며, 실제 잔액은 차감하지 않는다.
    async def check_bid_funds(
        self,
        *,
        bidder_id: int,
        amount: int,
        current_bidder_id: int | None,
        current_bid_amount: int | None,
    ) -> None:
        ...

    # 구매자·판매자·낙찰가를 받아 구매자 차감과 판매자 지급을 요청한다.
    # 수수료 없이 낙찰가 전액을 이전한다. 거래 기록과 아이템 이전은 포함하지 않는다.
    # 정상 종료하면 DB 변경이 반영된 상태이며, 최종 확정은 호출자가 한다.
    async def settle_sale(
        self,
        *,
        buyer_id: int,
        seller_id: int,
        price: int,
    ) -> None:
        ...


# 경매에서 필요한 아이템 예약 해제·이전·조회 기능의 계약이다.
class InventoryGateway(Protocol):
    # 아이템·소유자·매물 ID와 처리 시각을 받아 판매 예약을 요청한다.
    # 소유권·상태·재판매 제한은 인벤토리가 검사한다.
    # 반환: 예약된 아이템의 종류·이름·시작가를 담은 ItemSummary.
    async def reserve(
        self,
        inventory_item_id: int,
        owner_id: int,
        listing_id: int | None,
        now: datetime,
    ) -> ItemSummary:
        ...

    # 아이템·소유자·매물 ID와 처리 시각으로 예약을 해제한다.
    # 반환값 없음.
    async def release(
        self,
        inventory_item_id: int,
        owner_id: int,
        listing_id: int,
        now: datetime,
    ) -> None:
        ...

    # 아이템·판매자·구매자·매물 ID와 처리 시각으로 예약 아이템을 이전한다.
    # 반환값 없음.
    async def transfer_reserved(
        self,
        inventory_item_id: int,
        from_user_id: int,
        to_user_id: int,
        listing_id: int,
        now: datetime,
    ) -> None:
        ...

    # 아이템 ID로 거래 기록에 필요한 정보를 조회한다.
    # 반환: 아이템 ID·종류 ID·이름이 담긴 DTO.
    async def get_summary(
        self,
        inventory_item_id: int,
    ) -> ItemSummary:
        ...


# 관련 저장 작업을 함께 확정하거나 되돌리는 기능의 계약이다.
class TransactionManager(Protocol):
    # 현재 트랜잭션의 변경을 확정한다. 추가 입력과 반환값 없음.
    async def commit(self) -> None:
        ...

    # 현재 트랜잭션의 미확정 변경을 되돌린다. 추가 입력과 반환값 없음.
    async def rollback(self) -> None:
        ...
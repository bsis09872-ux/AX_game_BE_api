# Contract: 경매가 외부에 요청하는 기능의 입력값과 반환값을 정의한다.
# Protocol은 계약만 선언하며 실제 조회·저장·잠금은 구현체가 담당한다.
# 외부 데이터는 dto.py의 형태로 전달받고 다른 도메인의 ORM에 의존하지 않는다.
#
# AuctionUserGateway: 사용자 조회와 낙찰 제한 상태 저장.
# WalletGateway: 잔액 확인과 재화 이전.
# InventoryGateway: 판매 예약·해제·소유권 이전과 아이템 정보 조회.
# TransactionManager: 관련 변경의 확정과 되돌리기.
#
# 합의한 잠금 순서: 매물 → 아이템 → 사용자 → 지갑.
# 여러 사용자를 잠글 때는 사용자 ID 오름차순으로 처리한다.
# [TO DO] 필요한 잠금을 위 순서로 획득하도록 실제 호출 흐름을 연결한다.
# [TO DO] Gateway와 Repository가 같은 트랜잭션을 공유하도록 조립한다.
# [TO DO] 다음 PR에서 Adapter를 구현하고 서비스에 주입한다.
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
    # [TO DO] 요청한 사용자가 없을 때의 처리 방식을 Adapter 구현 전에 확정한다.
    async def get_for_update_many(
        self,
        user_ids: list[int],
    ) -> dict[int, AuctionUserState]:
        ...

    # 사용자 ID와 계산된 낙찰 횟수·제한 종료 시각을 받아 저장 요청한다.
    # 반환값 없음. commit은 트랜잭션 담당자가 수행한다.
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


# 경매에서 필요한 잔액 확인·재화 이전 기능의 계약이다.
# [TO DO] Wallet의 check_bid_funds·settle_sale 기준으로 이름·인자를 Wallet 담당자와 맞춘다. (진행 전)
# 입찰 확인에는 매물의 현재 최고 입찰자·입찰액도 넘겨야 한다.

class WalletGateway(Protocol):
    # 사용자 ID와 필요한 금액으로 잔액이 충분한지 확인한다.
    # 반환: 충분하면 True, 부족하면 False.
    async def has_balance(
        self,
        user_id: int,
        amount: int,
    ) -> bool:
        ...

    # 보내는 사용자·받는 사용자·금액을 받아 재화를 이전한다.
    # 반환값 없음. commit은 트랜잭션 담당자가 수행한다.
    async def transfer(
        self,
        from_user_id: int,
        to_user_id: int,
        amount: int,
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
    # 반환값 없음. commit은 트랜잭션 담당자가 수행한다.
    async def release(
        self,
        inventory_item_id: int,
        owner_id: int,
        listing_id: int,
        now: datetime,
    ) -> None:
        ...

    # 아이템·판매자·구매자·매물 ID와 처리 시각으로 예약 아이템을 이전한다.
    # 반환값 없음. commit은 트랜잭션 담당자가 수행한다.
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
# [TO DO] Adapter와 Repository가 같은 트랜잭션을 공유하도록 연결한다.
class TransactionManager(Protocol):
    # 현재 트랜잭션의 변경을 확정한다. 추가 입력과 반환값 없음.
    async def commit(self) -> None:
        ...

    # 현재 트랜잭션의 미확정 변경을 되돌린다. 추가 입력과 반환값 없음.
    async def rollback(self) -> None:
        ...
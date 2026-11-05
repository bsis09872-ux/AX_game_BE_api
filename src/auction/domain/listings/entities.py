# 매물의 생성·입찰·상태 전이 규칙을 담당한다.

# 완료한 체크 항목은 테스트 확인 후 삭제하고 역할·README 안내는 유지한다.

# [ ] ListingStatus: QUEUED / BIDDING / SOLD / FAILED 정의
# [ ] AUCTION_DURATION(6분), _ALLOWED_TRANSITIONS 정의
# [ ] Listing dataclass: README 필드 표 적용 (필수 필드 먼저, 기본값 필드 뒤)
# [ ] _ensure_aware: 시간 입력 규칙 검증
# [ ] _require_status: 현재 상태 검증
# [ ] _transition_to: 허용된 전이만 수행하고 updated_at = now 갱신
# [ ] create — AUC-01: 시작가 검증 후 QUEUED 생성, created_at·updated_at = now
# [ ] start — AUC-01, AUC-06: 공개·마감 시각 설정 후 _transition_to로 전환
# [ ] place_bid — AUC-04: README 검사 순서·예외 코드 적용
#     모든 검사 통과 후 최고 입찰자·입찰액 변경, 메서드 안에서 updated_at = now
# [ ] is_expired — AUC-05: return self.ends_at is not None and now >= self.ends_at
#     ends_at=None이면 예외 없이 False 반환
# [ ] has_bidder — AUC-05: 입찰자 존재 여부 반환
# [ ] remaining — AUC-03: 진행 중 남은 시간, 그 외 None 반환
# [ ] mark_sold — AUC-05: 마감·입찰자 확인 후 SOLD 전환 및 종료 시각 기록
# [ ] mark_failed — AUC-05: 마감 확인 후 FAILED 전환 및 종료 시각 기록
# [ ] 테스트: 정상·금지 전이, 마감 정각, 입찰 금액 경계
# [ ] 테스트: ends_at=None의 is_expired는 False
# [ ] 테스트: 성공한 5개 행위의 updated_at 갱신, 조회·실패 시 기존 값 유지

# 책임 경계: 소유권·재판매 제한은 inventory, 잔액 확인·정산 조율은 application.
# updated_at은 DB onupdate에 맡기지 않고 도메인의 now로 설정한다.

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from shared.core.exceptions import BusinessRuleError, ConflictError

# 매물 상태 정의 클래스
class ListingStatus(str, Enum):
    QUEUED = "QUEUED"
    BIDDING = "BIDDING"
    SOLD = "SOLD"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED" # QUEUED 인 매물만 취소 처리 가능하게 추가

# 경매 진행 시간 (상수)
AUCTION_DURATION = timedelta(minutes=6)

# 상태 전이 (허용 범위)
_ALLOWED_TRANSITIONS = {
    ListingStatus.QUEUED: {
        ListingStatus.BIDDING,
        ListingStatus.CANCELLED},
    ListingStatus.BIDDING: {
        ListingStatus.SOLD,
        ListingStatus.FAILED,
    },
    ListingStatus.SOLD: set(),
    ListingStatus.FAILED: set(),
    ListingStatus.CANCELLED: set(),
}

# 매물 필드 명세
@dataclass
class Listing:
    seller_id: int
    inventory_item_id: int
    item_definition_id: int
    start_price: int
    created_at: datetime

    status: ListingStatus = ListingStatus.QUEUED
    current_bidder_id: int | None = None
    current_bid_amount: int | None = None
    started_at: datetime | None = None
    ends_at: datetime | None = None
    closed_at: datetime | None = None
    updated_at: datetime | None = None
    id: int | None = None

    # [AUC-01] 판매자가 아이템을 등록할 때 대기 매물을 만든다.
    @classmethod
    def create(
        cls,
        seller_id: int,
        inventory_item_id: int,
        item_definition_id: int,
        start_price: int,
        now: datetime,
    ) -> "Listing":
        cls._ensure_aware(now)

        if start_price <= 0:
            raise BusinessRuleError("시작가는 0보다 커야 합니다.")

        return cls(
            seller_id=seller_id,
            inventory_item_id=inventory_item_id,
            item_definition_id=item_definition_id,
            start_price=start_price,
            created_at=now,
            updated_at=now,
        )

# [AUC-01, AUC-06] 대기 매물을 공개할 때 입찰을 시작하고 마감 시각을 정한다.
def start(self, now: datetime) -> None:
    self._require_status(ListingStatus.QUEUED)
    self._ensure_aware(now)
    ends_at = now + AUCTION_DURATION

    self._transition_to(ListingStatus.BIDDING, now)
    self.started_at = now
    self.ends_at = ends_at

# 판매자가 공개 전 본인 매물을 취소할 때 취소 상태로 바꾼다.
def cancel(self, requester_id: int, now: datetime) -> None:
    self._require_status(ListingStatus.QUEUED)
    self._ensure_aware(now)

    if requester_id != self.seller_id:
        raise BusinessRuleError("본인의 매물만 취소할 수 있습니다.")

    self._transition_to(ListingStatus.CANCELLED, now)
    self.closed_at = now

# [AUC-04] 새 입찰이 들어오면 조건을 검사하고 최고 입찰을 갱신한다.
def place_bid(self, bidder_id: int, amount: int, now: datetime) -> None:
    self._require_status(ListingStatus.BIDDING)

    if self.is_expired(now):
        raise ConflictError("입찰 시간이 종료되었습니다.")
    if bidder_id == self.seller_id:
        raise BusinessRuleError("자기 매물에는 입찰할 수 없습니다.")
    if bidder_id == self.current_bidder_id:
        raise ConflictError("현재 최고 입찰자는 다시 입찰할 수 없습니다.")

    if not self.has_bidder():
        if amount <= self.start_price:
            raise BusinessRuleError("입찰가는 시작가보다 커야 합니다.")
    elif amount <= self.current_bid_amount:
        raise ConflictError("현재 최고 입찰가보다 높게 입찰해야 합니다.")

    self.current_bidder_id = bidder_id
    self.current_bid_amount = amount
    self.updated_at = now

# [AUC-05] 마감 후 정산이 성공하면 낙찰 완료 상태로 바꾼다.
def mark_sold(self, now: datetime) -> None:
    self._require_status(ListingStatus.BIDDING)

    if not self.is_expired(now):
        raise ConflictError("마감 전에는 종료할 수 없습니다.")
    if not self.has_bidder():
        raise ConflictError("입찰자가 없는 매물은 낙찰 처리할 수 없습니다.")

    self._transition_to(ListingStatus.SOLD, now)
    self.closed_at = now

# [AUC-05] 마감 후 입찰자가 없거나 정산이 실패하면 유찰 처리한다.
def mark_failed(self, now: datetime) -> None:
    self._require_status(ListingStatus.BIDDING)

    if not self.is_expired(now):
        raise ConflictError("마감 전에는 종료할 수 없습니다.")

    self._transition_to(ListingStatus.FAILED, now)
    self.closed_at = now

# [AUC-04, AUC-05] 입찰·종료 처리 전에 마감 시각 도달 여부를 확인한다.
def is_expired(self, now: datetime) -> bool:
    self._ensure_aware(now)
    return self.ends_at is not None and now >= self.ends_at

# [AUC-04, AUC-05] 입찰 금액 검사와 낙찰 처리에 필요한 입찰자 존재 여부를 확인한다.
def has_bidder(self) -> bool:
    return self.current_bidder_id is not None

# [AUC-03] 매물 조회 시 보여줄 남은 시간을 계산한다.
def remaining(self, now: datetime) -> timedelta | None:
    self._ensure_aware(now)

    if self.status != ListingStatus.BIDDING:
        return None

    return max(self.ends_at - now, timedelta(0))

# 상태를 바꿀 때 허용된 전이인지 검사하고 변경 시각을 기록한다.
def _transition_to(self, new_status: ListingStatus, now: datetime) -> None:
    if new_status not in _ALLOWED_TRANSITIONS[self.status]:
        raise ConflictError("허용되지 않은 매물 상태 변경입니다.")

    self._ensure_aware(now)
    self.status = new_status
    self.updated_at = now

# 행위를 실행하기 전에 필요한 상태인지 확인한다.
def _require_status(self, expected: ListingStatus) -> None:
    if self.status != expected:
        raise ConflictError(f"{expected.value} 상태에서만 실행할 수 있습니다.")

# 시간 계산 전에 전달받은 시각이 UTC인지 확인한다.
@staticmethod
def _ensure_aware(now: datetime) -> None:
    offset = now.utcoffset()

    if offset is None:
        raise ValueError("now에는 시간대 정보가 필요합니다.")
    if offset != timedelta(0):
        raise ValueError("now는 UTC 시각이어야 합니다.")
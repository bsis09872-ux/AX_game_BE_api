# 낙찰이 확정된 거래를 변경 불가능한 기록으로 보존한다.

# 완료한 체크 항목은 테스트 확인 후 삭제하고 역할·README 안내는 유지한다.

# [x] Trade: README 필드 표에 맞춰 frozen dataclass 정의 (저장 전 id=None)
# [x] from_sold_listing: SOLD 상태와 필수 값 누락 검증
# [x] 양수 낙찰가·시간 입력 규칙 검증
# [x] 판매자·구매자·낙찰가·이름 스냅샷·체결 시각 저장
# [ ] 테스트: 확정 매물의 값과 스냅샷이 정확히 복사되는지 확인
# [ ] 테스트: 잘못된 상태·필수 값 누락·유효하지 않은 낙찰가 거부
# [ ] 테스트: 생성 후 필드 변경 불가 확인

# 책임 경계: 정산은 application, 매물당 거래 1건의 DB 제약은 infrastructure.


from dataclasses import dataclass
from datetime import datetime, timedelta

from auction.domain.listings.entities import Listing, ListingStatus
from shared.core import exceptions


# 1. 거래 기록 — 생성 후 값을 변경하지 않는다.
@dataclass(frozen=True)
class Trade:
    listing_id: int
    seller_id: int
    buyer_id: int
    item_name_snapshot: str
    seller_name_snapshot: str
    buyer_name_snapshot: str
    price_snapshot: int
    completed_at: datetime

    id: int | None = None

    # 2. [AUC-05] 정산이 끝난 SOLD 매물로 체결 당시의 거래 기록을 만든다.
    @classmethod
    def from_sold_listing(
        cls,
        listing: Listing,
        item_name: str,
        seller_name: str,
        buyer_name: str,
        now: datetime,
    ) -> "Trade":
        if listing.status != ListingStatus.SOLD:
            raise exceptions.ConflictError(
                "낙찰 완료된 매물만 거래 기록을 만들 수 있습니다."
            )

        cls._ensure_aware(now)

        if listing.id is None:
            raise ValueError("거래 기록을 만들려면 매물 ID가 필요합니다.")
        if listing.current_bidder_id is None:
            raise ValueError("낙찰 완료된 매물에 낙찰자가 없습니다.")
        if listing.current_bid_amount is None:
            raise ValueError("낙찰 완료된 매물에 낙찰가가 없습니다.")
        if listing.current_bid_amount <= 0:
            raise ValueError("낙찰 완료된 매물의 낙찰가는 0보다 커야 합니다.")

        return cls(
            listing_id=listing.id,
            seller_id=listing.seller_id,
            buyer_id=listing.current_bidder_id,
            item_name_snapshot=item_name,
            seller_name_snapshot=seller_name,
            buyer_name_snapshot=buyer_name,
            price_snapshot=listing.current_bid_amount,
            completed_at=now,
        )

    # 3. 거래 시각을 기록하기 전에 전달받은 시각이 UTC인지 확인한다.
    @staticmethod
    def _ensure_aware(now: datetime) -> None:
        offset = now.utcoffset()

        if offset is None:
            raise ValueError("now에는 시간대 정보가 필요합니다.")
        if offset != timedelta(0):
            raise ValueError("now는 UTC 시각이어야 합니다.")
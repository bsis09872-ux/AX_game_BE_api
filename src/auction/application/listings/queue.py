# 같은 아이템 종류의 대기열(QUEUED) 처리를 정산·유찰·관리자 취소가 함께 쓴다.
# 호출자는 먼저 현재 매물을 잠그고, 종류 잠금(lock_definition)을 건 뒤 호출해야 한다.
# 잠금 순서: 매물 → 종류 → 다음 대기 매물 → 아이템 → 사용자 → 지갑.
# commit·rollback은 호출자가 한다.

from auction.domain.listings.entities import Listing, ListingStatus
from auction.domain.listings.repositories import ListingRepository


# 같은 종류에서 다음으로 공개할 가장 오래된 대기 매물을 잠금 조회한다.
# 입력: 매물 Repository·아이템 종류 ID. 반환: 잠금된 QUEUED 매물, 없으면 None.
# 순서는 created_at → id(FIFO). 잠금 사이에 취소된 후보는 건너뛰고 다음 후보를 찾는다.
async def lock_next_queued(
    listings: ListingRepository,
    item_definition_id: int,
) -> Listing | None:
    while True:
        candidate = await listings.next_queued(item_definition_id)
        if candidate is None:
            return None

        locked = await listings.get_for_update(candidate.id)
        if locked is not None and locked.status == ListingStatus.QUEUED:
            return locked

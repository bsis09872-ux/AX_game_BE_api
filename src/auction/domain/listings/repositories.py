# 매물 저장·조회 Repository 인터페이스만 정의한다.

# 완료한 체크 항목은 테스트 확인 후 삭제하고 역할·README 안내는 유지한다.

# [ ] ListingRepository ABC 정의, 메서드별 입력·반환 타입 및 abstractmethod 선언
# [ ] get: 단건 조회, 없으면 None
# [ ] get_for_update: 수정 작업용 잠금 조회, 없으면 None
# [ ] list_bidding: 공개 중인 매물 목록
# [ ] exists_bidding: 같은 종류 공개 매물 존재 여부
# [ ] next_queued: 같은 종류의 가장 오래된 대기 매물
# [ ] list_expired_bidding: 마감 시각에 도달한 진행 매물
# [ ] sum_leading_bids: 사용자가 최고 입찰자인 진행 매물의 입찰액 합
# [ ] save: 매물 저장 및 엔티티 반환
# [ ] 목록 조회의 page 입력 계약을 application·infrastructure와 확인

# 책임 경계: SQL·잠금 실행·DB 제약·인덱스는 infrastructure에 구현한다.

from abc import ABC, abstractmethod
from datetime import datetime

from auction.domain.listings.entities import Listing


class ListingRepository(ABC):
    # [AUC-03] 매물 상세 정보가 필요할 때 조회한다. 없으면 None을 반환한다.
    @abstractmethod
    async def get(self, listing_id: int) -> Listing | None:
        ...

    # [AUC-04, AUC-05, AUC-11] 입찰·마감·취소 전에 매물을 잠금 조회한다.
    @abstractmethod
    async def get_for_update(self, listing_id: int) -> Listing | None:
        ...

    # [AUC-02] 경매장 목록에 표시할 BIDDING 매물을 페이지별로 조회한다.
    @abstractmethod
    async def list_bidding(self, page: int) -> list[Listing]:
        ...

    # [AUC-01, AUC-06] 대기 매물을 공개하기 전에 같은 종류의 진행 매물이 있는지 확인한다.
    @abstractmethod
    async def exists_bidding(self, item_definition_id: int) -> bool:
        ...

    # [AUC-06] 다음 공개 대상을 고를 때 같은 종류의 가장 오래된 대기 매물을 조회한다.
    @abstractmethod
    async def next_queued(self, item_definition_id: int) -> Listing | None:
        ...

    # [AUC-05] 마감 처리 대상을 찾을 때 종료 시각에 도달한 BIDDING 매물을 조회한다.
    @abstractmethod
    async def list_expired_bidding(self, now: datetime) -> list[Listing]:
        ...

    # [AUC-04] 입찰 가능 금액을 계산할 때 현재 최고 입찰로 묶인 금액을 합산한다.
    @abstractmethod
    async def sum_leading_bids(self, user_id: int) -> int:
        ...

    # 매물을 새로 등록하거나 변경한 뒤 저장하고 엔티티를 반환한다.
    @abstractmethod
    async def save(self, listing: Listing) -> Listing:
        ...
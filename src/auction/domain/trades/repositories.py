# 거래 기록을 저장하고 조회하는 계약을 정의한다. SQL은 infrastructure에서 구현한다.
# 신규 거래 저장은 ID가 반영된 새 Trade를 반환하며, 기존 거래는 수정하지 않는다.
# [TO DO] find_win_times_between을 인프라 Repository에 구현한다.
# [TO DO] 페이지 번호·페이지 크기 계약을 application과 맞춘다.
# [TO DO] 새 정책 연결 후 recent_win_times의 사용 여부를 확인하고 정리한다.

from abc import ABC, abstractmethod
from datetime import datetime

from auction.domain.trades.entities import Trade


# application이 거래 저장소를 사용하기 위한 인터페이스다.
# 구현체는 아래 메서드를 모두 제공하며 commit은 호출부에서 조율한다.
class TradeRepository(ABC):
    # [AUC-05] 정산 후 신규 거래를 저장하고 ID가 채워진 새 Trade를 반환한다.
    # flush로 저장하더라도 최종 commit까지 완료됐다는 의미는 아니다.
    @abstractmethod
    async def save(self, trade: Trade) -> Trade:
        ...

    # 매물에 연결된 거래 기록이 필요할 때 조회한다. 없으면 None을 반환한다.
    # 이 조회만으로 동시 중복 저장을 막지는 않으며 DB UNIQUE 제약도 필요하다.
    @abstractmethod
    async def get_by_listing(self, listing_id: int) -> Trade | None:
        ...

    # [AUC-07] 구매자의 낙찰 내역을 체결 시각 최신순으로 조회한다.
    # 같은 체결 시각이면 ID 내림차순으로 정렬하고, 결과가 없으면 빈 리스트다.
    @abstractmethod
    async def list_by_buyer(self, buyer_id: int, page: int) -> list[Trade]:
        ...

    # [AUC-10] 판매자의 판매 내역을 체결 시각 최신순으로 조회한다.
    # 같은 체결 시각이면 ID 내림차순으로 정렬하고, 결과가 없으면 빈 리스트다.
    @abstractmethod
    async def list_by_seller(self, seller_id: int, page: int) -> list[Trade]:
        ...

    # 매물·구매자·판매자 ID로 거래 내역을 필터링해 페이지별로 조회한다.
    # None인 조건은 생략하며, 여러 조건은 모두 만족해야 한다.
    # 체결 시각 최신순, 같은 시각이면 ID 내림차순으로 반환한다.
    # 권한은 서비스에서 검사하고, 결과가 없으면 빈 목록을 반환한다.
    @abstractmethod
    async def list_filtered(
        self,
        page: int,
        *,
        listing_id: int | None = None,
        buyer_id: int | None = None,
        seller_id: int | None = None,
    ) -> list[Trade]:
        ...

    # [AUC-08] 낙찰 제한을 계산할 때 구매자의 기간 내 낙찰 시각 전체를 조회한다.
    # since와 until은 UTC이며 since <= completed_at <= until인 기록을 반환한다.
    # 오래된 순으로 반환하고 같은 시각의 여러 거래도 각각 포함한다.
    # 결과가 없으면 빈 리스트다. 최신 3건으로 제한하거나 중복 시각을 제거하지 않는다.
    # application은 이번 낙찰 저장 후 조회하여 해당 거래가 한 번만 포함되게 한다.
    @abstractmethod
    async def find_win_times_between(
        self,
        buyer_id: int,
        since: datetime,
        until: datetime,
    ) -> list[datetime]:
        ...

    # 기존 계약: 최근 낙찰 시각을 최신순으로 최대 limit개 조회한다.
    # 기간 전체를 반환하지 않으므로 B 방식의 유효 횟수 집계에는 사용하지 않는다.
    # [TO DO] 호출부 전환을 확인한 뒤 이 계약과 인프라 구현을 함께 정리한다.
    @abstractmethod
    async def recent_win_times(
        self,
        buyer_id: int,
        limit: int,
    ) -> list[datetime]:
        ...
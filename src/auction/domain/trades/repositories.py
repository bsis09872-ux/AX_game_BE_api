# 거래 기록 저장·조회 Repository 인터페이스만 정의한다.

# 완료한 체크 항목은 테스트 확인 후 삭제하고 역할·README 안내는 유지한다.

# [ ] TradeRepository ABC 정의, 메서드별 입력·반환 타입 및 abstractmethod 선언
# [ ] save: 저장된 ID가 반영된 Trade 반환
# [ ] get_by_listing: 매물의 거래 기록, 없으면 None
# [ ] list_by_buyer: 구매자의 낙찰 내역 최신순 조회
# [ ] list_by_seller: 판매자의 판매 내역 최신순 조회
# [ ] recent_win_times: 최근 낙찰 시각 최신순으로 최대 limit개 반환
# [ ] 목록 조회의 page 입력 계약을 application·infrastructure와 확인

# 책임 경계: SQL·DB 제약·인덱스는 infrastructure에 구현한다.
# 저장 ID 반영은 README의 dataclasses.replace 기준을 따른다.

from abc import ABC, abstractmethod
from datetime import datetime

from auction.domain.trades.entities import Trade


class TradeRepository(ABC):
    # [AUC-05] 정산 후 만든 거래 기록을 저장하고 ID가 반영된 Trade를 반환한다.
    @abstractmethod
    async def save(self, trade: Trade) -> Trade:
        ...

    # 매물에 연결된 거래 기록을 확인할 때 조회한다. 없으면 None을 반환한다.
    @abstractmethod
    async def get_by_listing(self, listing_id: int) -> Trade | None:
        ...

    # [AUC-07] 내 낙찰 내역을 보여줄 때 구매자의 거래를 체결 시각 최신순으로 조회한다.
    @abstractmethod
    async def list_by_buyer(self, buyer_id: int, page: int) -> list[Trade]:
        ...

    # [AUC-10] 내 판매 내역을 보여줄 때 판매자의 거래를 체결 시각 최신순으로 조회한다.
    @abstractmethod
    async def list_by_seller(self, seller_id: int, page: int) -> list[Trade]:
        ...

    # [AUC-08] 새 입찰 제한을 판단할 때 최근 낙찰 시각을 최신순으로 최대 limit개 가져온다.
    @abstractmethod
    async def recent_win_times(
        self,
        buyer_id: int,
        limit: int,
    ) -> list[datetime]:
        ...
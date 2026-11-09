"""지갑 저장소 계약. 구현은 infrastructure/repositories.py

저장소는 commit하지 않는다. 트랜잭션 확정은 호출 측(요청 처리나 다른 도메인의 유스케이스)이 한다.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal

from wallet.domain.wallet import Wallet #TradeRecord

RoleFilter = Literal["buy", "sell", "all"]


class WalletRepository(ABC):
    # ---------- wallets ----------
    @abstractmethod
    async def get(self, user_id: int) -> Wallet | None: ...

    @abstractmethod
    async def save(self, user_id: int, balance: int) -> Wallet: ...

    @abstractmethod
    async def create(self, user_id: int, balance: int) -> Wallet:
        """지갑 1개 추가. 같은 user_id 지갑이 이미 있으면 DB PK 위반(IntegrityError)"""

    @abstractmethod
    async def create_if_absent(self, user_id: int, balance: int) -> Wallet | None:
        """지갑이 없으면 만들어 돌려주고, 이미 있으면 None. 동시 호출에도 PK 위반이 나지 않는다.

        회원이 없으면(users FK 위반) WalletNotFoundError.
        """

    @abstractmethod
    async def lock(self, user_ids: list[int]) -> dict[int, Wallet]:
        """지갑들을 FOR UPDATE로 잠근다. 데드락을 피하려고 항상 user_id 오름차순으로 잠근다."""

    # 예약 금액(held_amount)은 다른 도메인(auction) 데이터라 이 저장소에서 뺐다.
    # → application/contracts.py의 HeldAmountReader

    # @abstractmethod
    # async def lock(self, user_ids: list[int]) -> dict[int, Wallet]:
    #     """지갑들을 FOR UPDATE로 잠근다. 데드락을 피하려고 항상 user_id 오름차순으로 잠근다."""

    # @abstractmethod
    # async def create(self, user_id: int, balance: int) -> Wallet: ...

    # @abstractmethod
    # async def set_balance(self, user_id: int, balance: int) -> None: ...

    # # ---------- 다른 도메인 테이블 조회 ----------
    # @abstractmethod
    # async def held_amount(self, user_id: int) -> int:
    #     """내가 current_bidder_id인 BIDDING 매물의 current_bid_amount 합계 (없으면 0)"""

    # @abstractmethod
    # async def display_names(self, user_ids: list[int]) -> dict[int, str]: ...

    # @abstractmethod
    # async def item_name(self, item_definition_id: int) -> str | None: ...

    # # ---------- trades ----------
    # @abstractmethod
    # async def list_trades(
    #     self, user_id: int, role: RoleFilter, offset: int, limit: int
    # ) -> tuple[list[TradeRecord], int]:
    #     """최신순(completed_at DESC, id DESC) 한 페이지와 전체 개수"""

    # @abstractmethod
    # async def get_trade(self, trade_id: int) -> TradeRecord | None: ...

    # @abstractmethod
    # async def insert_trade(
    #     self,
    #     *,
    #     listing_id: int,
    #     buyer_id: int,
    #     item_name: str,
    #     seller_name: str,
    #     buyer_name: str,
    #     price: int,
    #     completed_at: datetime,
    # ) -> int:
    #     """trades 1행 추가 후 trade_id 반환. 같은 listing_id면 DB UNIQUE 위반"""

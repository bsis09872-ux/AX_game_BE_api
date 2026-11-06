"""서비스가 돌려주는 결과. presentation의 응답 스키마가 이 속성을 그대로 읽는다."""
from dataclasses import dataclass, field
from datetime import datetime

from wallet.application.balance_log import BalanceChange


@dataclass(frozen=True)
class WalletView:
    """WALL-01"""
    user_id: int
    balance: int
    held_amount: int
    available_balance: int
    updated_at: datetime


@dataclass(frozen=True)
class TradeListRow:
    """WALL-04 한 행"""
    trade_id: int
    role: str
    listing_id: int
    item_name: str
    counterpart_name: str
    price: int
    completed_at: datetime


@dataclass(frozen=True)
class TradePage:
    items: list[TradeListRow]
    page: int
    size: int
    total: int


@dataclass(frozen=True)
class TradeDetailView:
    """WALL-05"""
    trade_id: int
    listing_id: int
    item_name: str
    seller_name: str
    buyer_name: str
    price: int
    completed_at: datetime
    my_role: str
    my_balance_change: int


@dataclass(frozen=True)
class CreatedWallet:
    """WALL-06. 호출자가 commit 성공 뒤 log_balance_changes(balance_changes)를 호출한다."""
    user_id: int
    balance: int
    balance_changes: list[BalanceChange] = field(default_factory=list)


@dataclass(frozen=True)
class SettlementResult:
    """WALL-08 낙찰 정산 결과. 호출자가 commit 성공 뒤 log_balance_changes(balance_changes)를 호출한다."""
    trade_id: int
    buyer_id: int
    price: int
    balance_changes: list[BalanceChange] = field(default_factory=list)

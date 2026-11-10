"""서비스가 돌려주는 결과. presentation의 응답 스키마가 이 속성을 그대로 읽는다."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class WalletView:
    """WALL-02 내 지갑 조회 결과"""
    user_id: int
    balance: int
    held_amount: int
    available_balance: int
    updated_at: datetime

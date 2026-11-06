"""지갑 ORM 모델 (ERD Ver_4.0 wallets)

지갑 도메인이 소유하는 테이블은 wallets 하나다.
다른 도메인 테이블(listings, trades, users, item_definitions)은 external_tables.py에서
조회용으로만 가볍게 참조한다.
예약금 테이블(wallet_holds)과 잔액 원장(wallet_entries)은 Ver_4.0에서 삭제됐다.
"""
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class WalletModel(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_wallets_balance_non_negative"),
    )

    # 계정당 지갑 최대 1개: user_id가 곧 PK
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), primary_key=True
    )
    # 예약금을 포함한 총잔액. 예약 합계는 listings에서 계산하므로 여기 저장하지 않는다
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # balance가 바뀔 때만 갱신. 입찰로 예약 합계가 바뀌어도 그대로다
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"WalletModel(user_id={self.user_id}, balance={self.balance})"

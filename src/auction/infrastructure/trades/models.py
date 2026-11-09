# 정산이 끝난 거래의 스냅샷을 저장한다.
# 같은 auction의 listing_id만 FK로 연결하고, 매물당 거래 1건을 보장한다.
# 판매자·구매자는 ID만 저장하며 다른 도메인 모델을 참조하지 않는다.
# 거래 수정 기능은 제공하지 않는다. ORM 자체가 수정을 차단하는 것은 아니다.
# 테이블 생성 전에 Listing·Trade 모델을 모두 공통 metadata에 등록해야 한다.

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


# 정산이 끝난 거래의 체결 당시 값을 저장하는 테이블 모델이다.
class TradeModel(Base):
    __tablename__ = "trades"

    # 1. 식별자 — 같은 auction 내부의 매물만 FK로 연결한다.
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    listing_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("listings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    seller_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    buyer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # 2. 스냅샷 — 원본 이름이 바뀌어도 거래 당시 값을 유지한다.
    item_name_snapshot: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    seller_name_snapshot: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    buyer_name_snapshot: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    price_snapshot: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )

    # 3. 체결 시각 — application이 전달한 도메인의 시각을 저장한다.
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # 4. DB 제약과 조회용 인덱스
    __table_args__ = (
        # 같은 매물에 거래 기록이 중복 저장되는 것을 막는다.
        UniqueConstraint(
            "listing_id",
            name="uq_trades_listing_id",
        ),

        # 낙찰가는 양수여야 한다.
        CheckConstraint(
            "price_snapshot > 0",
            name="ck_trades_price_positive",
        ),

        # 내 낙찰 내역과 최근 낙찰 시각을 조회한다.
        Index(
            "ix_trades_buyer_completed",
            "buyer_id",
            "completed_at",
        ),

        # 내 판매 내역을 조회한다.
        Index(
            "ix_trades_seller_completed",
            "seller_id",
            "completed_at",
        ),
    )
# 매물 저장 구조와 DB 제약을 정의한다.
# 다른 도메인은 ID만 저장하며 FK·relationship으로 연결하지 않는다.
# 상태 판단은 domain, 엔티티 변환과 잠금 조회는 infrastructure Repository 담당.
# 시간 값은 도메인에서 전달받으며 DB의 현재 시각·onupdate를 사용하지 않는다.
# 조건부 UNIQUE 인덱스는 PostgreSQL 기준이다.

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


# 매물 엔티티의 값을 DB에 저장할 때 사용하는 테이블 모델이다.
class ListingModel(Base):
    __tablename__ = "listings"

    # 1. 식별자 — 다른 도메인의 객체 대신 ID 값만 저장한다.
    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    seller_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    inventory_item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    item_definition_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # 2. 가격과 현재 최고 입찰
    start_price: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_bidder_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    current_bid_amount: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )

    # 3. 상태 — Repository에서 ListingStatus와 문자열을 변환한다.
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="QUEUED"
    )

    # 4. 시간 — 도메인에서 정한 값을 그대로 저장한다.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # 관리자 강제 취소 기록 — 내부 기록용이며 응답에 노출하지 않는다.
    # 취소 시각은 closed_at을 쓴다. 판매자 취소·정산·유찰이면 둘 다 NULL이다.
    admin_cancelled_by: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    admin_cancel_reason: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )

    # 5. DB 제약과 조회용 인덱스
    __table_args__ = (
        # 시작가는 양수여야 한다.
        CheckConstraint(
            "start_price > 0",
            name="ck_listings_start_price_positive",
        ),

        # 입찰이 있으면 시작가보다 높아야 한다.
        CheckConstraint(
            "current_bid_amount IS NULL OR current_bid_amount > start_price",
            name="ck_listings_bid_above_start_price",
        ),

        # 입찰자와 입찰액은 함께 존재하거나 함께 없어야 한다.
        CheckConstraint(
            "(current_bidder_id IS NULL AND current_bid_amount IS NULL) OR "
            "(current_bidder_id IS NOT NULL AND current_bid_amount IS NOT NULL)",
            name="ck_listings_bid_pair",
        ),

        # 정의된 상태만 저장한다.
        CheckConstraint(
            "status IN ('QUEUED', 'BIDDING', 'SOLD', 'FAILED', 'CANCELLED')",
            name="ck_listings_status",
        ),

        # 같은 아이템 종류는 BIDDING 매물이 최대 1개다.
        Index(
            "uq_listings_bidding_item_definition",
            "item_definition_id",
            unique=True,
            postgresql_where=text("status = 'BIDDING'"),
        ),

        # 같은 종류의 다음 대기 매물을 찾을 때 사용한다.
        Index(
            "ix_listings_queue",
            "item_definition_id",
            "status",
            "created_at",
        ),

        # 진행 중인 매물 중 마감 시각이 지난 대상을 찾는다.
        Index(
            "ix_listings_expiration",
            "status",
            "ends_at",
        ),

        # 사용자가 최고 입찰자인 진행 매물의 금액을 합산한다.
        Index(
            "ix_listings_leading_bids",
            "current_bidder_id",
            "status",
        ),
    )
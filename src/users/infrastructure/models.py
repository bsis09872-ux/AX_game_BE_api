from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('USER', 'ADMIN')",
            name="ck_users_role",
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger(), primary_key=True)

    login_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    password_hash: Mapped[str] = mapped_column(String(), nullable=False)

    display_name: Mapped[str] = mapped_column(String(), nullable=False)

    role: Mapped[str] = mapped_column(
        String(5), nullable=False, default="USER", server_default="USER"
    )

    auction_purchase_count: Mapped[int] = mapped_column(default=0, server_default="0")
    auction_blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

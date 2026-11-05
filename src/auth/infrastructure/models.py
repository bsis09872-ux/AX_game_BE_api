# 폐기된 JWT 식별자를 저장한다. 토큰 원문과 비밀번호는 기록하지 않는다.
from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class RevokedTokenModel(Base):
    __tablename__ = "revoked_tokens"

    jti: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

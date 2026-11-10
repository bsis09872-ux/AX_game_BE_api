from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class WorldPresence(Base):
    __tablename__ = "world_presences"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), primary_key=True
    )
    connection_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    room: Mapped[str] = mapped_column(String(20))
    nickname: Mapped[str] = mapped_column(String(50))
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    face: Mapped[int] = mapped_column(Integer, default=1)
    direction: Mapped[str] = mapped_column(String(10), default="down")
    skin: Mapped[str] = mapped_column(String(20), default="angler")
    pose: Mapped[str] = mapped_column(String(10), default="idle")
    seq: Mapped[int] = mapped_column(BigInteger, default=-1)
    move_credit: Mapped[float] = mapped_column(Float, default=8)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    moved_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    cast_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))

    __table_args__ = (Index("ix_world_presences_room_updated", "room", "updated_at"),)


class FishingAttempt(Base):
    __tablename__ = "fishing_attempts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    connection_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    room: Mapped[str] = mapped_column(String(20))
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    bite_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="waiting")
    # 응답과 지급 아이템을 같은 트랜잭션에서 확정한다. 재요청에는 저장한 응답을 돌려준다.
    result: Mapped[dict | None] = mapped_column(JSONB)

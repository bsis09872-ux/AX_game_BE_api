"""행 잠금으로 여러 프로세스의 낚시 쿨다운을 공유한다. 호출자가 commit한다."""

import math
from datetime import datetime, timedelta

from sqlalchemy import BigInteger, ForeignKey, func, select
from sqlalchemy.dialects.postgresql import TIMESTAMP, insert
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class FishingCooldownModel(Base):
    __tablename__ = "fishing_cooldowns"
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), primary_key=True
    )
    available_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))


class SharedFishingCooldown:
    def __init__(self, session):
        self.session = session

    async def try_start(self, user_id: int, now: datetime) -> int:
        await self.session.execute(
            insert(FishingCooldownModel)
            .values(
                user_id=user_id,
                available_at=now,
            )
            .on_conflict_do_nothing(index_elements=["user_id"])
        )
        row = await self.session.scalar(
            select(FishingCooldownModel)
            .where(
                FishingCooldownModel.user_id == user_id,
            )
            .with_for_update()
        )
        current = await self.session.scalar(select(func.clock_timestamp()))
        remaining = math.ceil((row.available_at - current).total_seconds())
        if remaining > 0:
            return remaining
        row.available_at = current + timedelta(seconds=10)
        await self.session.flush()
        return 0

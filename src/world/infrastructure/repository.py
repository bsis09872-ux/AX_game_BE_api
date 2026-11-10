from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert

from world.domain.rules import MAP_NAMES
from world.infrastructure.models import FishingAttempt, WorldPresence


class WorldRepository:
    def __init__(self, session):
        self.session = session

    async def now(self):
        return await self.session.scalar(select(func.clock_timestamp()))

    async def lock_room(self, room):
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(:room)"),
            {"room": 91000 + MAP_NAMES.index(room)},
        )

    async def lock_player(self, user_id):
        row = (
            (
                await self.session.execute(
                    select(WorldPresence.__table__)
                    .where(
                        WorldPresence.user_id == user_id,
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        return dict(row) if row else None

    async def save_player(self, player):
        statement = insert(WorldPresence).values(**player)
        await self.session.execute(
            statement.on_conflict_do_update(
                index_elements=["user_id"],
                set_={key: value for key, value in player.items() if key != "user_id"},
            )
        )

    async def players(self, room, since):
        rows = (
            await self.session.execute(
                select(WorldPresence.__table__)
                .where(
                    WorldPresence.room == room,
                    WorldPresence.updated_at >= since,
                )
                .order_by(WorldPresence.user_id)
            )
        ).mappings()
        return [
            {
                "id": str(row["user_id"]),
                "nickname": row["nickname"],
                "x": row["x"],
                "y": row["y"],
                "face": row["face"],
                "direction": row["direction"],
                "skin": row["skin"],
                "pose": row["pose"],
                "seq": row["seq"],
            }
            for row in rows
        ]

    async def connection_alive(self, user_id, connection):
        return (
            await self.session.scalar(
                select(WorldPresence.connection_id).where(
                    WorldPresence.user_id == user_id
                )
            )
            == connection
        )

    async def leave(self, user_id, connection):
        # 이전 소켓의 finally가 새 연결을 지우지 않도록 연결 세대까지 비교한다.
        await self.session.execute(
            delete(WorldPresence).where(
                WorldPresence.user_id == user_id,
                WorldPresence.connection_id == connection,
            )
        )
        await self.commit()

    async def lock_attempt(self, attempt_id):
        row = (
            (
                await self.session.execute(
                    select(FishingAttempt.__table__)
                    .where(
                        FishingAttempt.id == attempt_id,
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        return dict(row) if row else None

    async def create_attempt(self, attempt):
        statement = (
            insert(FishingAttempt)
            .values(**attempt)
            .on_conflict_do_nothing(
                index_elements=["id"],
            )
            .returning(FishingAttempt.id)
        )
        return await self.session.scalar(statement) is not None

    async def save_attempt(self, attempt):
        await self.session.execute(
            update(FishingAttempt)
            .where(
                FishingAttempt.id == attempt["id"],
                FishingAttempt.user_id == attempt["user_id"],
            )
            .values(status=attempt["status"], result=attempt["result"])
        )

    async def cancel_attempt(self, attempt_id):
        await self.session.execute(
            update(FishingAttempt)
            .where(
                FishingAttempt.id == attempt_id,
                FishingAttempt.status == "waiting",
            )
            .values(status="cancelled")
        )

    async def commit(self):
        await self.session.commit()

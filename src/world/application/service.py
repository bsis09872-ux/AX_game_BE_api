"""접속, 이동, 낚시 시도를 조율한다. 저장/잠금은 repository에 맡긴다."""

import math
import secrets
from datetime import timedelta
from uuid import uuid4

from inventory.domain.exceptions import NoFishableDefinitionError
from world.domain.rules import PRESENCE_TTL, ROOM_CAPACITY, WALK_SPEED, WorldError


class WorldService:
    def __init__(self, repository, geometry, rewards=None, present_reward=None):
        self.repository = repository
        self.geometry = geometry
        self.rewards = rewards
        self.present_reward = present_reward

    async def join(self, user_id, nickname, room, skin):
        geometry = self.geometry(room)
        await self.repository.lock_room(room)
        now = await self.repository.now()
        players = await self.repository.players(
            room, now - timedelta(seconds=PRESENCE_TTL)
        )
        if sum(player["id"] != str(user_id) for player in players) >= ROOM_CAPACITY:
            raise WorldError("ROOM_FULL", "낚시터가 가득 찼습니다.")

        previous = await self.repository.lock_player(user_id)
        x, y = geometry.spawn
        if (
            previous
            and previous["room"] == room
            and geometry.can_stand(previous["x"], previous["y"])
        ):
            x, y = previous["x"], previous["y"]
        if previous and previous["cast_id"]:
            await self.repository.cancel_attempt(previous["cast_id"])

        connection = uuid4()
        await self.repository.save_player(
            {
                "user_id": user_id,
                "connection_id": connection,
                "room": room,
                "nickname": nickname,
                "x": x,
                "y": y,
                "face": 1,
                "direction": "down",
                "skin": skin,
                "pose": "idle",
                "seq": -1,
                "move_credit": 8.0,
                "updated_at": now,
                "moved_at": now,
                "cast_id": None,
            }
        )
        await self.repository.commit()
        return {
            "connection_id": str(connection),
            "id": str(user_id),
            "x": x,
            "y": y,
            "room": room,
        }

    async def _connected_player(self, user_id, connection):
        player = await self.repository.lock_player(user_id)
        now = await self.repository.now()
        if (
            not player
            or player["connection_id"] != connection
            or (now - player["updated_at"]).total_seconds() > PRESENCE_TTL
        ):
            raise WorldError("WORLD_DISCONNECTED", "낚시터 연결을 확인해 주세요.")
        return player, now

    async def move(self, user_id, connection, move):
        player, now = await self._connected_player(user_id, connection)
        if move.seq <= player["seq"]:
            return None

        geometry = self.geometry(player["room"])
        distance = math.hypot(move.x - player["x"], move.y - player["y"])
        # 여유 거리를 메시지마다 새로 주지 않고 누적 예산으로 제한한다.
        credit = min(
            20.0,
            player["move_credit"]
            + max(0, (now - player["moved_at"]).total_seconds()) * WALK_SPEED * 1.15,
        )
        accepted = distance <= credit and geometry.can_travel(
            player["x"], player["y"], move.x, move.y
        )
        player.update(seq=move.seq, updated_at=now, moved_at=now, move_credit=credit)

        if accepted:
            if distance > 0.1 and player["cast_id"]:
                await self.repository.cancel_attempt(player["cast_id"])
                player["cast_id"] = None
            player.update(
                x=move.x,
                y=move.y,
                face=move.face,
                direction=move.direction,
                skin=move.skin,
                pose=move.pose,
                move_credit=credit - distance,
            )

        await self.repository.save_player(player)
        await self.repository.commit()
        return (
            None
            if accepted
            else {
                "type": "correct",
                "x": player["x"],
                "y": player["y"],
                "seq": move.seq,
            }
        )

    async def begin_cast(self, user_id, connection, attempt_id):
        player, now = await self._connected_player(user_id, connection)
        attempt = await self.repository.lock_attempt(attempt_id)
        if attempt:
            if attempt["user_id"] != user_id or attempt["connection_id"] != connection:
                raise WorldError("CAST_NOT_FOUND", "낚시 시도를 찾을 수 없습니다.", 404)
            return self._cast_view(attempt, now)

        if not self.geometry(player["room"]).near_water(player["x"], player["y"]):
            raise WorldError("NOT_NEAR_WATER", "호숫가에서 낚시해 주세요.", 400)
        if player["cast_id"]:
            previous = await self.repository.lock_attempt(player["cast_id"])
            if (
                previous
                and previous["status"] == "waiting"
                and previous["expires_at"] >= now
            ):
                raise WorldError("CAST_ACTIVE", "진행 중인 낚시가 있습니다.")

        # DB 기록을 공유하여 프로세스/재접속을 바꿔도 쿨다운을 우회할 수 없다.
        remaining = await self.rewards.start_cooldown(user_id, now)
        if remaining:
            raise WorldError(
                "FISHING_COOLDOWN", "잠시 후 다시 던져 주세요.", 429, remaining
            )
        bite_at = now + timedelta(milliseconds=550 + 2000 + secrets.randbelow(3001))
        attempt = {
            "id": attempt_id,
            "user_id": user_id,
            "connection_id": connection,
            "room": player["room"],
            "x": player["x"],
            "y": player["y"],
            "bite_at": bite_at,
            "expires_at": bite_at + timedelta(seconds=1),
            "status": "waiting",
            "result": None,
        }
        if not await self.repository.create_attempt(attempt):
            raise WorldError("CAST_CONFLICT", "다른 낚시 시도와 ID가 겹쳤습니다.")
        player["cast_id"] = attempt_id
        await self.repository.save_player(player)
        await self.repository.commit()
        return self._cast_view(attempt, now)

    @staticmethod
    def _cast_view(attempt, now):
        return {
            "id": str(attempt["id"]),
            "server_time": now.isoformat(),
            "bite_at": attempt["bite_at"].isoformat(),
            "expires_at": attempt["expires_at"].isoformat(),
            "status": attempt["status"],
        }

    async def cancel_cast(self, user_id, connection, attempt_id):
        player, _ = await self._connected_player(user_id, connection)
        if player["cast_id"] == attempt_id:
            await self.repository.cancel_attempt(attempt_id)
            player["cast_id"] = None
            await self.repository.save_player(player)
        await self.repository.commit()

    async def catch(self, user_id, attempt_id):
        # 모든 경로의 잠금 순서는 player -> attempt로 유지한다.
        player = await self.repository.lock_player(user_id)
        attempt = await self.repository.lock_attempt(attempt_id)
        if not attempt or attempt["user_id"] != user_id:
            raise WorldError("CAST_NOT_FOUND", "낚시 시도를 찾을 수 없습니다.", 404)
        if attempt["result"] is not None:
            return attempt["result"]

        now = await self.repository.now()
        if (
            not player
            or player["connection_id"] != attempt["connection_id"]
            or player["cast_id"] != attempt_id
            or (now - player["updated_at"]).total_seconds() > PRESENCE_TTL
        ):
            raise WorldError("WORLD_DISCONNECTED", "낚시터에 다시 연결해 주세요.")
        if attempt["status"] != "waiting":
            raise WorldError("CAST_FINISHED", "이미 끝난 낚시입니다.")

        # 먼저/늦게 당기거나 위치가 바뀌면 해당 시도는 소모한다.
        valid_time = attempt["bite_at"] <= now <= attempt["expires_at"]
        valid_position = (
            math.hypot(player["x"] - attempt["x"], player["y"] - attempt["y"]) <= 0.1
        )
        if not valid_time or not valid_position:
            attempt["status"] = "missed"
            await self.repository.save_attempt(attempt)
            await self.repository.commit()
            raise WorldError(
                "FISHING_MISSED", "입질 시기를 놓쳤거나 위치가 바뀌었습니다."
            )

        # 이미 투척 시 쿨다운을 소비했으므로 여기서는 지급만 준비한다.
        try:
            item = await self.rewards.prepare_verified_reward(user_id, now)
        except NoFishableDefinitionError as error:
            raise WorldError(error.code, error.message, 503) from error
        result = self.present_reward(item)
        attempt.update(status="caught", result=result)
        await self.repository.save_attempt(attempt)
        await self.repository.commit()
        return result

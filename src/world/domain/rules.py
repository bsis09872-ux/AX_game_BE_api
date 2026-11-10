"""월드 이동과 낚시 판정에 사용하는 서버 규칙."""

import math
from dataclasses import dataclass

MAP_NAMES = ("world", "lake", "halloween")
SKINS = ("angler", "girl", "girl_blue", "boy", "ghost", "ranger", "knight")
WALK_SPEED = 60.0
PRESENCE_TTL = 15
ROOM_CAPACITY = 30


class WorldError(Exception):
    def __init__(
        self, code: str, message: str, status: int = 409, retry_after: int = 0
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.retry_after = retry_after


@dataclass
class MapGeometry:
    width: int
    height: int
    blocked: bytearray
    water: set[tuple[int, int]]
    spawn: tuple[float, float]

    def can_stand(self, x: float, y: float) -> bool:
        if x + 3 < 0 or y < 0 or x + 13 > self.width or y + 16 > self.height:
            return False
        return not any(
            self.blocked[row * self.width + column]
            for row in range(math.floor(y + 10), math.floor(y + 15) + 1)
            for column in range(math.floor(x + 3), math.floor(x + 12) + 1)
        )

    def can_travel(self, start_x: float, start_y: float, x: float, y: float) -> bool:
        steps = max(1, math.ceil(math.hypot(x - start_x, y - start_y)))
        return all(
            self.can_stand(
                start_x + (x - start_x) * step / steps,
                start_y + (y - start_y) * step / steps,
            )
            for step in range(1, steps + 1)
        )

    def near_water(self, x: float, y: float) -> bool:
        feet_x, feet_y = x + 8, y + 13
        column, row = math.floor(feet_x / 16), math.floor(feet_y / 16)
        for r in range(row - 3, row + 4):
            for c in range(column - 3, column + 4):
                if (c, r) not in self.water:
                    continue
                dx = max(c * 16 - feet_x, 0, feet_x - (c + 1) * 16)
                dy = max(r * 16 - feet_y, 0, feet_y - (r + 1) * 16)
                if math.hypot(dx, dy) <= 10:
                    return True
        return False

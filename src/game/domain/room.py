"""방 하나 = 맵 하나

- 들어온 사람 명단과 이번 틱에 바뀐 사람을 기억한다
- 서버 한 대의 메모리에만 둔다 (서버를 여러 대 띄우면 방도 따로 생긴다)
"""

from game.domain.exceptions import AlreadyInRoomError, RoomFullError
from game.domain.player import Player


class Room:
    def __init__(self, name: str, capacity: int):
        self.name = name
        self.capacity = capacity
        self.players: dict[int, Player] = {}
        self._dirty: set[int] = set()

    def __len__(self) -> int:
        return len(self.players)

    def join(self, player: Player) -> None:
        if player.user_id in self.players:
            raise AlreadyInRoomError()
        if len(self.players) >= self.capacity:
            raise RoomFullError(f"이 맵은 {self.capacity}명까지 들어올 수 있어요. 잠시 후 다시 시도해 주세요.")
        self.players[player.user_id] = player

    def leave(self, user_id: int) -> Player | None:
        self._dirty.discard(user_id)
        return self.players.pop(user_id, None)

    def mark_moved(self, user_id: int) -> None:
        self._dirty.add(user_id)

    def take_changes(self) -> list[dict]:
        """이번 틱에 움직인 사람만 꺼낸다. 아무도 안 움직였으면 빈 목록 → 아무것도 보내지 않는다."""
        changed = [self.players[uid].view(with_name=False) for uid in self._dirty if uid in self.players]
        self._dirty.clear()
        return changed

    def snapshot(self, except_id: int | None = None) -> list[dict]:
        """새로 들어온 사람에게 보내는 전체 명단. 아직 첫 위치를 안 보낸 사람은 뺀다."""
        return [p.view() for uid, p in self.players.items() if uid != except_id and p.placed]

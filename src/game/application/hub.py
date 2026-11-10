"""멀티플레이 허브: 접속한 사람들을 방(맵)별로 묶고, 위치를 모아 1초에 tick_hz번 나눠 준다

- WebSocket을 직접 모른다. 연결마다 보낼 메시지 대기열(Connection)만 다루므로 가짜 연결로 테스트할 수 있다
- 서버 한 대의 메모리에만 둔다. 서버를 다시 켜면 모두 다시 접속한다

흐름:
    join  → welcome(나 + 이미 있는 사람들)을 나에게
    move  → 첫 위치면 join을 다른 사람에게, 아니면 이번 틱에 바뀐 사람으로 표시
    skin  → 캐릭터를 바꾸면 이번 틱에 바뀐 사람으로 표시
    틱    → 바뀐 사람만 모아 state 한 통으로 (자기 자신은 빼고)
    leave → leave를 다른 사람에게
"""

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable

from game.domain.exceptions import TooFastError
from game.domain.player import Move, Player
from game.domain.room import Room

logger = logging.getLogger(__name__)

# 연결 종료 코드. 4000~4999는 앱이 정해서 쓴다. 브라우저는 이 숫자로 재연결할지 정한다
CLOSE_NORMAL = 1000
CLOSE_POLICY = 1008  # 규칙 위반(형식, 횟수 초과 등) → 재연결 안 함
CLOSE_TOO_BIG = 1009  # 메시지가 너무 큼 → 재연결 안 함
CLOSE_TRY_LATER = 1013  # 방이 꽉 참, 너무 느림 → 잠시 후 재연결
CLOSE_UNAUTHORIZED = 4401  # 로그인 안 됨·만료 → 세션을 새로 고친 뒤 재연결
CLOSE_FORBIDDEN_ORIGIN = 4403  # 다른 사이트에서 연결 → 재연결 안 함
CLOSE_REPLACED = 4409  # 같은 계정이 다른 곳에서 접속 → 재연결 안 함


def error_message(code: str, message: str) -> dict:
    """HTTP 오류와 같은 {"detail": {code, message}} 모양으로 WebSocket 오류를 보낸다."""
    return {"type": "error", "detail": {"code": code, "message": message}}


class _Close:
    def __init__(self, code: int, reason: str):
        self.code = code
        self.reason = reason


class Connection:
    """한 사람의 연결. push로 대기열에 넣으면 run_writer가 순서대로 보낸다.

    보내기를 한 작업(writer)에서만 하므로, 받는 쪽과 틱이 동시에 보내도 섞이지 않는다.
    """

    def __init__(
        self,
        user_id: int,
        nickname: str,
        send_text: Callable[[str], Awaitable[None]],
        close: Callable[[int, str], Awaitable[None]],
        queue_size: int,
    ):
        self.user_id = user_id
        self.nickname = nickname
        self._send_text = send_text
        self._close = close
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self.closing = False
        self.room: Room | None = None
        self.player: Player | None = None

    def push(self, message: dict) -> None:
        if self.closing:
            return
        try:
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            # 인터넷이 느려 대기열이 꽉 찼다. 한 사람 때문에 방 전체가 느려지면 안 되니 이 사람만 끊는다
            logger.warning("world_slow_client user_id=%s", self.user_id)
            self.close(CLOSE_TRY_LATER, "TOO_SLOW")

    def close(self, code: int, reason: str) -> None:
        """종료를 대기열 끝에 넣는다(앞서 넣은 오류 안내는 먼저 나간다). 꽉 찼으면 비우고 넣는다. 실제로 닫는 건 writer가 한다."""
        if self.closing:
            return
        self.closing = True
        if self._queue.full():
            while not self._queue.empty():
                self._queue.get_nowait()
        self._queue.put_nowait(_Close(code, reason))

    async def run_writer(self) -> None:
        while True:
            item = await self._queue.get()
            if isinstance(item, _Close):
                await self._close(item.code, item.reason)
                return
            await self._send_text(json.dumps(item, ensure_ascii=False, separators=(",", ":")))


class WorldHub:
    def __init__(self, tick_hz: int, room_capacity: int, clock: Callable[[], float] = time.monotonic):
        self.tick_hz = tick_hz
        self.room_capacity = room_capacity
        self.clock = clock
        self.rooms: dict[str, Room] = {}
        self.conns: dict[int, Connection] = {}  # 한 계정은 연결 하나만
        self._ticker: asyncio.Task | None = None

    # ---------- 들어오기·나가기 ----------
    def join(self, conn: Connection, map_name: str, skin: str = "angler") -> None:
        """방이 꽉 찼으면 RoomFullError를 던진다. 같은 계정의 예전 연결은 4409로 끊는다."""
        room = self.rooms.get(map_name) or Room(map_name, self.room_capacity)
        old = self.conns.get(conn.user_id)
        if old is not None:
            self._remove(old)
            old.push(error_message("REPLACED", "다른 곳에서 같은 계정으로 접속해서 연결을 끊었어요."))
            old.close(CLOSE_REPLACED, "REPLACED")
        player = Player(conn.user_id, conn.nickname, skin=skin)
        room.join(player)
        self.rooms[map_name] = room
        self.conns[conn.user_id] = conn
        conn.room, conn.player = room, player
        conn.push({
            "type": "welcome",
            "you": {"id": str(conn.user_id), "nickname": conn.nickname},
            "map": map_name,
            "tick_hz": self.tick_hz,
            "players": room.snapshot(except_id=conn.user_id),
        })
        logger.info("world_join user_id=%s map=%s players=%s", conn.user_id, map_name, len(room))
        self._ensure_ticker()

    def leave(self, conn: Connection) -> None:
        if self.conns.get(conn.user_id) is conn:
            self._remove(conn)

    def _remove(self, conn: Connection) -> None:
        self.conns.pop(conn.user_id, None)
        room, player = conn.room, conn.player
        if room is None or room.players.get(conn.user_id) is not player:
            return
        room.leave(conn.user_id)
        logger.info("world_leave user_id=%s map=%s players=%s", conn.user_id, room.name, len(room))
        if player.placed:
            self._broadcast(room, {"type": "leave", "id": str(conn.user_id)}, except_id=conn.user_id)
        if not room.players:
            self.rooms.pop(room.name, None)

    # ---------- 움직임 ----------
    def move(self, conn: Connection, move: Move) -> None:
        player, room = conn.player, conn.room
        if player is None or room is None:
            return
        was_placed = player.placed
        try:
            accepted = player.apply(move, self.clock())
        except TooFastError as exc:
            # 순간이동: 위치를 바꾸지 않고 본인에게 마지막 위치를 돌려준다
            conn.push({
                "type": "correct", "x": player.x, "y": player.y, "seq": player.seq,
                "detail": {"code": exc.code, "message": exc.message},
            })
            return
        if not accepted:
            return
        if was_placed:
            room.mark_moved(conn.user_id)
        else:
            self._broadcast(room, {"type": "join", "player": player.view()}, except_id=conn.user_id)

    def change_skin(self, conn: Connection, skin) -> None:
        """캐릭터를 바꾸면 다음 틱 state에 실어 다른 사람에게 알린다. 틀린 이름은 InvalidSkinError를 던진다."""
        player, room = conn.player, conn.room
        if player is None or room is None:
            return
        if player.change_skin(skin) and player.placed:
            room.mark_moved(conn.user_id)

    # ---------- 틱 ----------
    def tick(self) -> None:
        """방마다 이번 틱에 바뀐 사람을 한 통으로 묶어 보낸다. 자기 자신의 위치는 본인에게 보내지 않는다."""
        for room in list(self.rooms.values()):
            changes = room.take_changes()
            if not changes:
                continue
            for uid in room.players:
                conn = self.conns.get(uid)
                others = [c for c in changes if c["id"] != str(uid)]
                if conn and others:
                    conn.push({"type": "state", "players": others})

    def _ensure_ticker(self) -> None:
        if self._ticker is None or self._ticker.done():
            self._ticker = asyncio.create_task(self._run_ticker())

    async def _run_ticker(self) -> None:
        # 아무도 없으면 스스로 멈춘다. 다음 사람이 들어오면 join이 다시 켠다
        while self.conns:
            await asyncio.sleep(1 / self.tick_hz)
            self.tick()

    def _broadcast(self, room: Room, message: dict, except_id: int | None = None) -> None:
        for uid in room.players:
            conn = self.conns.get(uid)
            if conn and uid != except_id:
                conn.push(message)

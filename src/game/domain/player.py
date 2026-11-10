"""같은 맵(방)에 있는 사람의 위치·동작

- 서버가 마지막 위치를 기억하고, 순간이동과 순서가 뒤바뀐 낡은 메시지를 막는다
- 위치는 "보여 주기"용이다. 돈·아이템은 바꾸지 않는다 (낚시 결과는 POST /v1/fishing-results가 정한다)
- 외부 라이브러리를 쓰지 않는 순수 파이썬이라 DB·WebSocket 없이 테스트한다
"""

import math

from game.domain.exceptions import InvalidMoveError, InvalidSkinError, TooFastError

POSES = ("idle", "walk", "rod")  # 서 있음, 걷는 중, 낚싯대를 든 상태(찌가 물에 있을 수도 있음)
DIRS = ("down", "up", "side")  # 보는 방향: 앞모습, 뒷모습, 옆모습(좌우는 face)
# 고를 수 있는 캐릭터. 그림은 static/sprites/characters/char_<skin>[_up|_side].png (angler는 char_player)
SKINS = ("angler", "girl", "boy", "ghost", "ranger", "knight")

WALK_SPEED = 60  # 화면(static/game/play.js)의 SPEED와 같은 초당 픽셀
SPEED_TOLERANCE = 1.5  # 네트워크가 메시지를 몰아서 줘도 걸리지 않게 둔 여유 배수
SLACK_PX = 16  # 한 칸만큼의 여유
MAX_COORD = 10_000  # 맵이 아무리 커도 넘을 수 없는 좌표


def check_skin(skin) -> str:
    if skin not in SKINS:
        raise InvalidSkinError(f"캐릭터는 {', '.join(SKINS)} 중 하나여야 합니다.")
    return skin


def _number(value, name: str) -> float:
    # bool은 int의 자식이라 따로 막는다
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise InvalidMoveError(f"{name}는 숫자여야 합니다.")
    if not (-MAX_COORD <= value <= MAX_COORD):
        raise InvalidMoveError(f"{name}가 맵 밖입니다.")
    return float(value)


class Move:
    """브라우저가 보낸 "지금 여기 있어요". 변화량이 아니라 절대 좌표라 하나가 빠져도 다음 것이 덮어쓴다."""

    def __init__(self, seq, x, y, face=1, pose="idle", bobber=None, dir="down"):
        if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
            raise InvalidMoveError("seq는 0 이상의 정수여야 합니다.")
        if isinstance(face, bool) or face not in (1, -1):
            raise InvalidMoveError("face는 1 또는 -1이어야 합니다.")
        if dir not in DIRS:
            raise InvalidMoveError(f"dir는 {', '.join(DIRS)} 중 하나여야 합니다.")
        if pose not in POSES:
            raise InvalidMoveError(f"pose는 {', '.join(POSES)} 중 하나여야 합니다.")
        if bobber is not None:
            if pose != "rod" or not isinstance(bobber, (list, tuple)) or len(bobber) != 2:
                raise InvalidMoveError("찌 위치는 낚싯대를 들었을 때 [x, y]로만 보냅니다.")
            bobber = (_number(bobber[0], "bobber.x"), _number(bobber[1], "bobber.y"))
        self.seq = seq
        self.x = _number(x, "x")
        self.y = _number(y, "y")
        self.face = face
        self.pose = pose
        self.bobber = bobber
        self.dir = dir


class Player:
    def __init__(self, user_id: int, nickname: str, skin: str = "angler"):
        self.user_id = user_id
        self.nickname = nickname
        self.skin = check_skin(skin)
        self.x: float | None = None  # 첫 위치를 받기 전에는 None. 다른 사람 화면에 아직 그리지 않는다
        self.y: float | None = None
        self.face = 1
        self.dir = "down"
        self.pose = "idle"
        self.bobber: tuple[float, float] | None = None
        self.seq = -1
        self.moved_at: float | None = None  # 마지막으로 위치를 받아들인 시각 (초, 단조 시계)

    @property
    def placed(self) -> bool:
        return self.x is not None

    def apply(self, move: Move, now: float) -> bool:
        """받아들였으면 True, 이미 받은 것보다 오래된 메시지라 버렸으면 False.

        너무 빨리 움직였으면 TooFastError를 던진다. 위치는 바꾸지 않으므로 서버가 마지막 위치로 되돌려 주면 된다.
        """
        if move.seq <= self.seq:
            return False
        if self.placed:
            limit = WALK_SPEED * SPEED_TOLERANCE * max(0.0, now - self.moved_at) + SLACK_PX
            if math.hypot(move.x - self.x, move.y - self.y) > limit:
                self.seq = move.seq  # 같은 메시지를 다시 보내도 통과하지 않게 번호는 넘긴다
                raise TooFastError()
        self.seq = move.seq
        self.x, self.y = move.x, move.y
        self.face, self.dir, self.pose, self.bobber = move.face, move.dir, move.pose, move.bobber
        self.moved_at = now
        return True

    def change_skin(self, skin) -> bool:
        """바뀌었으면 True. 같은 캐릭터를 다시 고르면 다른 사람에게 알릴 필요가 없다."""
        if check_skin(skin) == self.skin:
            return False
        self.skin = skin
        return True

    def view(self, with_name: bool = True) -> dict:
        """다른 사람에게 보내는 모양. ID는 팀 규칙(JSON에서는 10진 문자열)대로 보낸다.

        위치 묶음(state)에는 닉네임을 빼서 메시지를 줄인다. 닉네임은 들어올 때(join·welcome) 한 번만 보낸다.
        """
        view = {
            "id": str(self.user_id),
            "x": self.x,
            "y": self.y,
            "face": self.face,
            "dir": self.dir,
            "pose": self.pose,
            "skin": self.skin,
            "bobber": list(self.bobber) if self.bobber else None,
        }
        if with_name:
            view["nickname"] = self.nickname
        return view

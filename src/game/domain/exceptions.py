"""낚시터(game) 도메인 예외

- 공통 분류(shared.core.exceptions)를 상속한다. HTTP로 나가면 공통 핸들러가 400·409로 바꾼다
- WebSocket에서는 HTTP 상태 대신 {"type": "error", "detail": {code, message}}로 보낸다 (presentation이 바꾼다)
- 외부 프레임워크를 참조하지 않는다
"""

from shared.core.exceptions import BusinessRuleError, ConflictError


class InvalidMoveError(BusinessRuleError):
    # 위치 메시지의 모양이 틀림 (숫자가 아님, 맵 밖, 모르는 동작 등)
    code: str = "INVALID_MOVE"
    message: str = "위치 정보가 올바르지 않습니다."


class TooFastError(BusinessRuleError):
    # 걷는 속도로는 갈 수 없는 거리를 한 번에 움직임 (순간이동)
    code: str = "TOO_FAST"
    message: str = "너무 빨리 움직였어요. 마지막 위치로 되돌립니다."


class InvalidSkinError(BusinessRuleError):
    # 고를 수 없는 캐릭터 이름
    code: str = "INVALID_SKIN"
    message: str = "고를 수 없는 캐릭터입니다."


class RoomFullError(ConflictError):
    # 한 맵에 들어올 수 있는 인원을 넘음
    code: str = "ROOM_FULL"
    message: str = "이 맵은 인원이 다 찼어요. 잠시 후 다시 시도해 주세요."


class AlreadyInRoomError(ConflictError):
    # 같은 회원이 같은 방에 두 번 들어옴 (허브가 예전 연결을 먼저 정리하므로 보통은 생기지 않는다)
    code: str = "ALREADY_IN_ROOM"
    message: str = "이미 이 맵에 있습니다."

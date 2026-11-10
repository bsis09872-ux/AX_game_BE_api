"""멀티플레이 WebSocket (앱에서 /v1 prefix 적용 후 /v1/ws/world)

같은 맵에 있는 사람들의 위치·낚시 동작을 주고받는다. "보여 주기"만 한다.
돈·아이템이 바뀌는 일(낚시 결과, 입찰)은 HTTP API가 한다.

로그인: 웹 화면과 같은 HttpOnly 쿠키(access_token)를 쓴다. 브라우저가 WebSocket 연결 요청에 쿠키를 자동으로 붙인다.
  - 토큰을 주소나 메시지에 담지 않는다 (JavaScript가 인증 정보를 다루지 않는다는 팀 규칙)
  - 쿠키가 자동으로 붙으므로 다른 사이트에서 연결하지 못하게 Origin을 확인한다 (WEB_ORIGIN)
  - 맵과 캐릭터는 비밀이 아니라서 주소로 받는다: /v1/ws/world?map=world&skin=angler

브라우저 → 서버                                    서버 → 브라우저
  {"type":"move","seq":1,"x":..,"y":..,            {"type":"welcome","you":{id,nickname},"map","tick_hz","players":[..]}
   "face":1,"dir":"side","pose":"walk",            {"type":"join","player":{..}} / {"type":"leave","id":"3"}
   "bobber":null}                                  {"type":"state","players":[바뀐 사람만]}  (1초에 tick_hz번)
  {"type":"skin","skin":"ghost"}                   {"type":"correct","x":..,"y":..,"seq":..,"detail":{..}} (순간이동 되돌림)
  {"type":"ping","t":123}                          {"type":"pong","t":123}
                                                   {"type":"error","detail":{"code","message"}}
종료 코드: 4401 로그인 필요, 4403 다른 사이트, 4409 다른 곳에서 접속, 1008 규칙 위반, 1009 너무 큼, 1013 잠시 후 다시
"""

import asyncio
import json
import logging
import re
from collections.abc import Callable

from fastapi import APIRouter, Depends, WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

from game.application.contracts import PlayerDirectory
from game.application.hub import (
    CLOSE_FORBIDDEN_ORIGIN,
    CLOSE_NORMAL,
    CLOSE_POLICY,
    CLOSE_TOO_BIG,
    CLOSE_TRY_LATER,
    CLOSE_UNAUTHORIZED,
    Connection,
    WorldHub,
    error_message,
)
from game.domain.player import Move, check_skin
from game.domain.rate_limit import MessageBudget
from game.presentation.dependencies import get_directory, get_hub
from game.wiring import MAX_MESSAGE_BYTES, SEND_QUEUE_SIZE
from shared.core.exceptions import AppError

logger = logging.getLogger(__name__)

MAP_NAME = re.compile(r"^[\w-]{1,32}$")
MOVES_PER_SECOND = 15  # 위치는 1초에 10번 보내므로 여유를 둔다
OTHERS_PER_SECOND = 5  # ping, skin


class _Reject(Exception):
    def __init__(self, close_code: int, code: str, message: str):
        self.close_code = close_code
        self.code = code
        self.message = message


async def _read(websocket: WebSocket) -> dict:
    """글자 메시지 하나를 JSON 객체로 읽는다. 끊기면 WebSocketDisconnect, 형식이 틀리면 _Reject."""
    message = await websocket.receive()
    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(message.get("code", CLOSE_NORMAL))
    text = message.get("text")
    if text is None:
        raise _Reject(CLOSE_POLICY, "TEXT_ONLY", "글자(JSON) 메시지만 받습니다.")
    if len(text.encode()) > MAX_MESSAGE_BYTES:
        raise _Reject(CLOSE_TOO_BIG, "MESSAGE_TOO_BIG", f"메시지는 {MAX_MESSAGE_BYTES}바이트까지 보낼 수 있어요.")
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("type"), str):
        raise _Reject(CLOSE_POLICY, "INVALID_MESSAGE", '{"type": ...} 모양의 JSON이어야 합니다.')
    return data


async def _reject(websocket: WebSocket, close_code: int, code: str, message: str) -> None:
    """보내기 담당(writer)이 생기기 전에 오류를 보내고 닫는다."""
    if websocket.client_state == WebSocketState.CONNECTED:
        try:
            await websocket.send_json(error_message(code, message))
            await websocket.close(close_code, code)
        except (WebSocketDisconnect, RuntimeError):
            pass


async def _finish(writer: asyncio.Task) -> None:
    """writer가 남은 메시지와 종료를 보내게 잠깐 기다린다. 상대가 이미 끊겼으면 보내기 실패는 무시한다."""
    try:
        await asyncio.wait_for(writer, 2)
    except Exception:  # noqa: BLE001 - 시간 초과나 끊긴 소켓에 쓰다 난 예외. 서버 로그를 더럽히지 않는다
        writer.cancel()


def create_world_router(allowed_origin: Callable[[], str]) -> APIRouter:
    """멀티플레이 WebSocket 라우터를 만든다.

    allowed_origin: 연결을 허용할 웹 주소를 돌려주는 함수 (auth의 get_web_settings().origin)
    """
    router = APIRouter(tags=["game"])

    @router.websocket("/ws/world")
    async def world(
        websocket: WebSocket,
        hub: WorldHub = Depends(get_hub),
        directory: PlayerDirectory = Depends(get_directory),
    ):
        await websocket.accept()

        # 1. 출처·주소·로그인 확인
        if websocket.headers.get("origin") != allowed_origin():
            return await _reject(websocket, CLOSE_FORBIDDEN_ORIGIN, "FORBIDDEN_ORIGIN", "허용되지 않은 요청 출처입니다.")
        map_name = websocket.query_params.get("map") or "world"
        if not MAP_NAME.match(map_name):
            return await _reject(websocket, CLOSE_POLICY, "INVALID_MAP", "맵 이름은 영문·숫자·_·- 32자까지입니다.")
        skin = websocket.query_params.get("skin") or "angler"
        try:
            check_skin(skin)
        except AppError as exc:
            return await _reject(websocket, CLOSE_POLICY, exc.code, exc.message)
        identity = await directory.authenticate(websocket.cookies.get("access_token", ""))
        if identity is None:
            return await _reject(websocket, CLOSE_UNAUTHORIZED, "UNAUTHORIZED", "로그인이 필요하거나 세션이 만료됐습니다.")

        # 2. 방에 들어가기. 여기부터 보내기는 전부 conn.push → writer 한 곳에서만 한다
        async def close(code: int, reason: str) -> None:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close(code, reason)

        conn = Connection(identity.user_id, identity.nickname, websocket.send_text, close, SEND_QUEUE_SIZE)
        writer = asyncio.create_task(conn.run_writer())
        try:
            hub.join(conn, map_name, skin)
        except AppError as exc:
            conn.push(error_message(exc.code, exc.message))
            conn.close(CLOSE_TRY_LATER, exc.code)
            await _finish(writer)
            return

        # 3. 끊길 때까지 받기
        moves, others = MessageBudget(MOVES_PER_SECOND), MessageBudget(OTHERS_PER_SECOND)
        try:
            while not conn.closing:
                data = await _read(websocket)
                kind = data["type"]
                budget = moves if kind == "move" else others
                if not budget.allow(hub.clock()):
                    raise _Reject(CLOSE_POLICY, "TOO_MANY_MESSAGES", "메시지를 너무 자주 보냈어요.")
                if kind == "move":
                    try:
                        move = Move(data.get("seq"), data.get("x"), data.get("y"), data.get("face", 1),
                                    data.get("pose", "idle"), data.get("bobber"), data.get("dir", "down"))
                    except AppError as exc:
                        conn.push(error_message(exc.code, exc.message))  # 형식이 틀린 위치 하나는 버리고 연결은 유지한다
                        continue
                    hub.move(conn, move)
                elif kind == "skin":
                    try:
                        hub.change_skin(conn, data.get("skin"))
                    except AppError as exc:
                        conn.push(error_message(exc.code, exc.message))  # 틀린 이름이면 알려 주고 연결은 유지한다
                elif kind == "ping":
                    conn.push({"type": "pong", "t": data.get("t")})
                else:
                    conn.push(error_message("UNKNOWN_TYPE", f"모르는 메시지 종류입니다: {kind[:20]}"))
        except _Reject as exc:
            logger.warning("world_reject code=%s user_id=%s", exc.code, conn.user_id)
            conn.push(error_message(exc.code, exc.message))
            conn.close(exc.close_code, exc.code)
        except (WebSocketDisconnect, RuntimeError):
            pass  # 탭을 닫거나 인터넷이 끊김. 아래에서 정리한다
        finally:
            hub.leave(conn)
            if not conn.closing:
                conn.close(CLOSE_NORMAL, "BYE")
            await _finish(writer)

    return router

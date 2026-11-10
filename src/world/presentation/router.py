"""짧은 DB 세션으로 접속 상태를 공유한다. 소켓 수명 동안 DB 연결을 점유하지 않는다."""

import asyncio
import json
import logging
import time
from contextlib import suppress
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from auth.domain.exceptions import AuthenticationError
from auth.presentation.web_dependencies import get_web_settings
from auth.wiring import build_auth_service
from database import AsyncSessionLocal
from users.wiring import build_user_service
from world.domain.rules import PRESENCE_TTL, WorldError
from world.infrastructure.repository import WorldRepository
from world.presentation.schemas import Hello, Move
from world.wiring import build_world_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/v1/ws/world")
async def world_socket(socket: WebSocket):
    if socket.headers.get("origin") != get_web_settings().origin:
        await socket.close(code=1008)
        return

    token = socket.cookies.get("access_token", "")
    connection = None
    tasks = []
    await socket.accept()
    send_lock = asyncio.Lock()

    async def send(message):
        async with send_lock:
            await asyncio.wait_for(socket.send_json(message), timeout=3)

    try:
        async with AsyncSessionLocal() as session:
            claims = await build_auth_service(session).authenticate(token)
            user = await build_user_service(session).get_user_summary(claims.user_id)
        raw = await asyncio.wait_for(socket.receive_text(), timeout=5)
        if len(raw) > 2048:
            await socket.close(code=1009)
            return
        hello = Hello.model_validate_json(raw)
        async with AsyncSessionLocal() as session:
            welcome = await build_world_service(session).join(
                claims.user_id, user.display_name, hello.room, hello.skin
            )
        connection = UUID(welcome["connection_id"])
        await send({"type": "welcome", **welcome})

        async def receive():
            window_started, count = time.monotonic(), 0
            while True:
                raw = await asyncio.wait_for(socket.receive_text(), timeout=12)
                if len(raw) > 2048:
                    await socket.close(code=1009)
                    return
                now = time.monotonic()
                if now - window_started >= 1:
                    window_started, count = now, 0
                count += 1
                if count > 25:
                    await socket.close(code=1008)
                    return
                message = json.loads(raw)
                if message == {"type": "ping"}:
                    await send({"type": "pong"})
                    continue
                move = Move.model_validate(message)
                async with AsyncSessionLocal() as session:
                    correction = await build_world_service(session).move(
                        claims.user_id, connection, move
                    )
                if correction:
                    await send(correction)

        async def broadcast():
            checked_at = time.monotonic()
            while True:
                async with AsyncSessionLocal() as session:
                    repository = WorldRepository(session)
                    if not await repository.connection_alive(
                        claims.user_id, connection
                    ):
                        await socket.close(
                            code=4409, reason="다른 창에서 접속했습니다."
                        )
                        return
                    if time.monotonic() - checked_at >= 5:
                        await build_auth_service(session).authenticate(token)
                        checked_at = time.monotonic()
                    now = await repository.now()
                    players = await repository.players(
                        hello.room, now - timedelta(seconds=PRESENCE_TTL)
                    )
                await send({"type": "state", "players": players})
                await asyncio.sleep(0.2)

        tasks = [asyncio.create_task(receive()), asyncio.create_task(broadcast())]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except AuthenticationError:
        with suppress(RuntimeError, WebSocketDisconnect):
            await socket.close(code=4401)
    except WorldError as error:
        with suppress(RuntimeError, WebSocketDisconnect):
            await send({"type": "error", "code": error.code, "message": error.message})
            await socket.close(code=1013)
    except (ValidationError, ValueError, TypeError):
        with suppress(RuntimeError, WebSocketDisconnect):
            await socket.close(code=1008)
    except (TimeoutError, WebSocketDisconnect):
        with suppress(RuntimeError, WebSocketDisconnect):
            await socket.close(code=1001)
    except Exception:
        logger.exception("world_connection_failed")
        with suppress(RuntimeError, WebSocketDisconnect):
            await socket.close(code=1011)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if connection:
            async with AsyncSessionLocal() as session:
                await WorldRepository(session).leave(claims.user_id, connection)

"""임시 PostgreSQL DB, 두 ASGI 프로세스와 두 독립 Chromium 계정으로 검증한다.

사용자 DB의 테이블/계정은 수정하지 않는다. 임시 DB 생성 권한이 필요하다.
uv run --frozen --with httpx --with playwright python scripts/verify-fishing-client.py
"""

import asyncio
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import asyncpg
import httpx
import websockets
from dotenv import load_dotenv
from playwright.async_api import async_playwright, expect
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from world.infrastructure.map_loader import load_geometry

ARTIFACTS = ROOT / ".private" / "multiplayer-qa"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
SCREENSHOTS = ARTIFACTS
def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


async def ready(base, process):
    async with httpx.AsyncClient() as client:
        for _ in range(100):
            assert process.poll() is None, (
                "QA server exited; see .private/multiplayer-qa logs"
            )
            try:
                if (await client.get(base + "/health")).status_code == 200:
                    return
            except httpx.RequestError:
                pass
            await asyncio.sleep(0.1)
    raise AssertionError("QA server startup timeout")


async def open_socket(base, client, room="world"):
    cookies = "; ".join(f"{key}={value}" for key, value in client.cookies.items())
    ws = await websockets.connect(
        base.replace("http", "ws") + "/v1/ws/world",
        origin=base,
        additional_headers={"Cookie": cookies},
    )
    await ws.send(json.dumps({"type": "hello", "room": room, "skin": "angler"}))
    welcome = await receive_type(ws, "welcome")
    return ws, welcome


async def receive_type(ws, kind):
    async with asyncio.timeout(5):
        while True:
            message = json.loads(await ws.recv())
            if message["type"] == kind:
                return message


async def send_move(ws, seq, x, y):
    await ws.send(
        json.dumps(
            {
                "type": "move",
                "seq": seq,
                "x": float(x),
                "y": float(y),
                "face": 1,
                "direction": "down",
                "skin": "angler",
                "pose": "idle",
            }
        )
    )


async def check_api(bases, clients, db, restart):
    a, b = clients
    # 미인증/다른 Origin、旧直接 지급 경로를 우회할 수 없다.
    async with httpx.AsyncClient(base_url=bases[0]) as guest:
        assert (await guest.get("/v1/play")).status_code == 303
        assert (
            await guest.post(
                "/v1/play/fishing-results",
                headers={"Origin": bases[0]},
                json={"cast_id": str(uuid4())},
            )
        ).status_code == 401
    for headers in ({"Origin": "https://other.invalid"}, {"Origin": ""}):
        assert (
            await a.post(
                "/v1/play/casts",
                headers=headers,
                json={"id": str(uuid4()), "connection_id": str(uuid4())},
            )
        ).status_code == 403
    assert (await a.post("/v1/play/fishing-results", json={})).status_code == 422
    assert (
        await a.post("/v1/play/fishing-results", json={"cast_id": str(uuid4())})
    ).status_code == 404
    bearer = {"Authorization": "Bearer " + a.cookies.get("access_token")}
    assert (
        await a.post("/v1/fishing-results", headers=bearer, json={})
    ).status_code == 422
    try:
        await websockets.connect(
            bases[0].replace("http", "ws") + "/v1/ws/world",
            origin="https://other.invalid",
        )
        raise AssertionError("foreign origin accepted")
    except websockets.exceptions.InvalidStatus:
        pass
    async with websockets.connect(
        bases[0].replace("http", "ws") + "/v1/ws/world", origin=bases[0]
    ) as guest_ws:
        with suppress(websockets.exceptions.ConnectionClosed):
            await guest_ws.recv()
        assert guest_ws.close_code == 4401

    ws, welcome = await open_socket(bases[0], a)
    try:
        # 새 계정의 스폰에서는 낚시가 불가능하다.
        body = {"id": str(uuid4()), "connection_id": welcome["connection_id"]}
        assert (await a.post("/v1/play/casts", json=body)).status_code == 400
        await send_move(ws, 0, 500, 300)
        corrected = await receive_type(ws, "correct")
        assert (corrected["x"], corrected["y"]) == (128, 96)
        # 실제 속도 범위 안에서 이동하여 서버 충돌 경계 바로 위까지 간다.
        for seq, y in enumerate(range(100, 145, 4), start=1):
            await asyncio.sleep(0.08)
            await send_move(ws, seq, 128, y)
        await asyncio.sleep(0.25)
        await send_move(ws, 13, 128, 148)
        corrected = await receive_type(ws, "correct")
        assert corrected["y"] == 144, corrected
        cast = await a.post("/v1/play/casts", json=body)
        assert cast.status_code == 200, cast.text
        result_body = {"cast_id": body["id"]}
        assert (
            await b.post("/v1/play/fishing-results", json=result_body)
        ).status_code == 404
        early = await a.post("/v1/play/fishing-results", json=result_body)
        assert early.status_code == 409, early.text
        # 두 번째 프로세스에서도 쿨다운을 공유한다.
        response = await a.post(
            bases[1] + "/v1/play/casts",
            headers={"Origin": bases[1]},
            json={**body, "id": str(uuid4())},
        )
        assert response.status_code == 429, response.text
        assert int(response.headers["Retry-After"]) > 0
        # 같은 계정의 새 연결이 이전 연결만 종료한다.
        newer, new_welcome = await open_socket(bases[1], a)
        try:
            while True:
                await ws.recv()
        except websockets.exceptions.ConnectionClosed:
            assert ws.close_code == 4409
        await send_move(newer, 0, 128, 144)
        state = await receive_type(newer, "state")
        assert any(p["id"] == new_welcome["id"] for p in state["players"])
        # 유한 좌표만 허용한다.
        await send_move(newer, 1, float("nan"), 144)
        try:
            while True:
                await newer.recv()
        except websockets.exceptions.ConnectionClosed:
            assert newer.close_code == 1008
        await newer.close()
    finally:
        await ws.close()
    # 실제 최초 지급을 두 프로세스에 동시에 요청한다.
    ws, welcome = await open_socket(bases[1], b)
    try:
        for seq, y in enumerate(range(100, 145, 4)):
            await asyncio.sleep(0.08)
            await send_move(ws, seq, 128, y)
        await asyncio.sleep(0.25)
        # 실패 주입용 DDL은 투척 전에 준비해 1초 입질 구간을 소모하지 않는다.
        await db.execute("""CREATE FUNCTION qa_reject_result() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.status = 'caught' THEN RAISE EXCEPTION 'QA rollback'; END IF; RETURN NEW; END; $$;
            CREATE TRIGGER qa_reject_result BEFORE UPDATE ON fishing_attempts FOR EACH ROW EXECUTE FUNCTION qa_reject_result();""")
        body = {"id": str(uuid4()), "connection_id": welcome["connection_id"]}
        cast = await b.post("/v1/play/casts", json=body)
        assert cast.status_code == 200, cast.text
        deadline = datetime.fromisoformat(cast.json()["bite_at"])
        await asyncio.sleep(
            max(0, (deadline - datetime.now(UTC)).total_seconds()) + 0.05
        )
        payload = {"cast_id": body["id"]}
        failed = await b.post("/v1/play/fishing-results", json=payload)
        assert failed.status_code == 500, failed.text
        assert await db.fetchval("SELECT count(*) FROM inventory_items") == 0
        assert await db.fetchval("SELECT count(*) FROM item_events") == 0
        await db.execute(
            "DROP TRIGGER qa_reject_result ON fishing_attempts; DROP FUNCTION qa_reject_result()"
        )
        replies = await asyncio.gather(
            *[
                b.post(
                    base + "/v1/play/fishing-results",
                    headers={"Origin": base},
                    json=payload,
                )
                for base in bases
            ]
        )
        assert all(response.status_code == 201 for response in replies), [
            r.text for r in replies
        ]
        assert replies[0].json()["id"] == replies[1].json()["id"]
        assert await db.fetchval("SELECT count(*) FROM inventory_items") == 1
        assert await db.fetchval("SELECT count(*) FROM item_events") == 1
        await restart(0)
        replay = await b.post(
            bases[0] + "/v1/play/fishing-results",
            headers={"Origin": bases[0]},
            json=payload,
        )
        assert replay.json()["id"] == replies[0].json()["id"]
        cooldown = await b.post(
            bases[0] + "/v1/play/casts",
            headers={"Origin": bases[0]},
            json={**body, "id": str(uuid4())},
        )
        assert cooldown.status_code == 429, cooldown.text
    finally:
        await ws.close()
    await db.execute("DELETE FROM item_events; DELETE FROM inventory_items")
    print(
        "PASS transactions: forced rollback, simultaneous first catch, reward/cooldown survive process restart",
        flush=True,
    )
    # 테스트 전용 DB 초기 상태 복원. 사용자 DB에는 이 SQL을 실행하지 않는다.
    await db.execute("TRUNCATE world_presences, fishing_attempts, fishing_cooldowns")
    print(
        "PASS API: authentication/origin, forged reward, teleport/wall/NaN, early bite, cross-owner, shared cooldown, connection generation",
        flush=True,
    )


async def check_browser(bases, clients, db, restart):
    from game_browser_qa import check_browser as check
    await check(bases, clients, db, restart, ARTIFACTS)


async def main():
    load_dotenv(ROOT / ".env.local")
    load_dotenv(ROOT / ".env")
    url = make_url(os.environ["DATABASE_URL"])
    connection_args = {
        "user": url.username,
        "password": url.password,
        "host": url.host,
        "port": url.port or 5432,
        "database": url.database,
    }
    admin = await asyncpg.connect(**connection_args)
    database_name = "ax_game_qa_" + uuid4().hex
    assert (
        database_name.startswith("ax_game_qa_")
        and database_name.replace("_", "").isalnum()
    )
    await admin.execute(f'CREATE DATABASE "{database_name}"')
    processes, logs, clients, environments = [], [], [], []
    db = None
    try:
        db = await asyncpg.connect(**{**connection_args, "database": database_name})
        bases = []
        for index in range(2):
            port = free_port()
            base = f"http://127.0.0.1:{port}"
            env = {
                **os.environ,
                "DATABASE_URL": url.set(database=database_name).render_as_string(
                    hide_password=False
                ),
                "WEB_ORIGIN": base,
                "DEMO_FISHING_ENABLED": "true",
                "JWT_SECRET_KEY": secrets.token_urlsafe(48),
            }
            # 두 프로세스가 같은 서명 설정을 공유한다.
            if index == 0:
                shared_secret = env["JWT_SECRET_KEY"]
            env["JWT_SECRET_KEY"] = shared_secret
            log = (ARTIFACTS / f"server-{index}.log").open("w", encoding="utf-8")
            logs.append(log)
            process = await asyncio.to_thread(
                subprocess.Popen,
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "main:app",
                    "--app-dir",
                    "src",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--ws-max-size",
                    "2048",
                ],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            processes.append(process)
            environments.append(env)
            await ready(base, process)
            bases.append(base)
        await db.execute(
            "INSERT INTO item_definitions(code,name,category,rarity,start_price,icon,weight,fishable) VALUES ('qa_fish','QA 물고기','FISH','COMMON',100,'fish_carp',1,true)"
        )
        for index, base in enumerate(bases):
            client = httpx.AsyncClient(
                base_url=base, headers={"Origin": base}, timeout=10
            )
            clients.append(client)
            values = {
                "login_id": f"qa_angler{index}",
                "display_name": f"QA 낚시꾼 {index + 1}",
                "password": secrets.token_urlsafe(24),
            }
            assert (await client.post("/register", data=values)).status_code == 303
            assert (
                await client.post(
                    "/login",
                    data={key: values[key] for key in ("login_id", "password")},
                )
            ).status_code == 303

        async def restart(index):
            process = processes[index]
            process.terminate()
            await asyncio.to_thread(process.wait, 5)
            await asyncio.sleep(0.5)
            processes[index] = await asyncio.to_thread(
                subprocess.Popen,
                process.args,
                cwd=ROOT,
                env=environments[index],
                stdout=logs[index],
                stderr=logs[index],
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            await ready(bases[index], processes[index])

        await check_api(bases, clients, db, restart)
        await check_browser(bases, clients, db, restart)
        print(
            "ALL PASS: temporary PostgreSQL + 2 ASGI processes + 2 Chromium sessions",
            flush=True,
        )
    finally:
        for client in clients:
            await client.aclose()
        for process in processes:
            process.terminate()
        for process in processes:
            with suppress(subprocess.TimeoutExpired):
                process.wait(timeout=5)
            if process.poll() is None:
                process.kill()
                process.wait()
        for log in logs:
            log.close()
        if db:
            await db.close()
        await admin.execute(f'DROP DATABASE "{database_name}" WITH (FORCE)')
        await admin.close()


if __name__ == "__main__":
    asyncio.run(main())

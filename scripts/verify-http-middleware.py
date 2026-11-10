"""DB와 서버 lifespan 없이 HTTP 미들웨어와 실제 앱 연결을 검증한다.

실행: uv run --frozen --with httpx python scripts/verify-http-middleware.py
"""

import asyncio
import logging
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import httpx
from fastapi import Depends, HTTPException, WebSocket
from fastapi.responses import StreamingResponse


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# 기존 .env 파일의 DB를 사용하지 않는다. ASGITransport는 lifespan을 실행하지 않는다.
os.environ["DATABASE_URL"] = "postgresql+asyncpg://qa:qa@127.0.0.1:1/middleware_test_unused"
os.environ["JWT_SECRET_KEY"] = "middleware-test-only-" * 4
os.environ["WEB_ORIGIN"] = "http://127.0.0.1:8000"
os.environ.pop("CORS_ALLOWED_ORIGINS", None)

from shared.core.http_application import HttpApplication
from shared.core.http_middleware import RequestLoggingMiddleware
from shared.core.http_settings import read_cors_origins
from shared.core.exception_handlers import register_exception_handlers
from auth.presentation.web_dependencies import require_web_origin


ORIGIN = "http://127.0.0.1:8000"
LOGGER = "shared.core.http_middleware"


def test_app():
    app = HttpApplication(cors_origins=[ORIGIN, "https://frontend.example.com"])
    register_exception_handlers(app)

    @app.get("/ok")
    async def ok(delay: float = 0):
        await asyncio.sleep(delay)
        return {"ok": True}

    @app.post("/cookie-write", dependencies=[Depends(require_web_origin)])
    async def cookie_write():
        return {"ok": True}

    @app.get("/status/{status}")
    async def status(status: int):
        raise HTTPException(status)

    @app.get("/failure")
    async def failure():
        raise RuntimeError("SECRET_EXCEPTION_CONTENT")

    @app.post("/echo")
    async def echo(body: dict):
        return body

    @app.get("/stream")
    async def stream():
        async def chunks():
            yield b"first"
            await asyncio.sleep(0)
            yield b"second"
        return StreamingResponse(chunks())

    @app.websocket("/ws")
    async def ws(socket: WebSocket):
        await socket.accept()
        await socket.send_text(await socket.receive_text())
        await socket.close()

    return app


class SettingsTests(unittest.TestCase):
    def test_default_and_explicit_empty(self):
        with patch.dict(os.environ, {"WEB_ORIGIN": ORIGIN}, clear=True):
            self.assertEqual(read_cors_origins(), [ORIGIN])
            os.environ["CORS_ALLOWED_ORIGINS"] = ""
            self.assertEqual(read_cors_origins(), [])

    def test_multiple_and_invalid_origins(self):
        with patch.dict(os.environ, {"CORS_ALLOWED_ORIGINS": f" {ORIGIN}/,https://app.example.com,{ORIGIN}"}):
            self.assertEqual(read_cors_origins(), [ORIGIN, "https://app.example.com"])
        for value in ["*", "null", "https://*.example.com", "https://example.com/path",
                      "https://a:b@example.com", "https://example.com?key=secret",
                      "https://example.com:99999", "https://exam ple.com", "file:///tmp"]:
            with self.subTest(value=value), patch.dict(os.environ, {"CORS_ALLOWED_ORIGINS": value}):
                with self.assertRaises(ValueError):
                    read_cors_origins()


class HttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = test_app()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app, raise_app_exceptions=False),
            base_url=ORIGIN,
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_preflight(self):
        with self.assertLogs(LOGGER, logging.INFO) as logs:
            response = await self.client.options("/echo", headers={
                "Origin": ORIGIN, "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], ORIGIN)
        self.assertEqual(response.headers["access-control-allow-credentials"], "true")
        self.assertIn("Origin", response.headers["vary"])
        self.assertGreaterEqual(float(response.headers["x-process-time"]), 0)
        self.assertEqual(len(logs.records), 1)

    async def test_disallowed_origin_and_headers(self):
        for origin, header in [("https://evil.example", "content-type"), (ORIGIN, "x-not-allowed")]:
            response = await self.client.options("/echo", headers={
                "Origin": origin, "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": header,
            })
            self.assertEqual(response.status_code, 400)
        response = await self.client.get("/ok", headers={"Origin": "https://evil.example"})
        self.assertNotIn("access-control-allow-origin", response.headers)

    async def test_cookie_origin_guard_not_weakened_by_cors(self):
        response = await self.client.post("/cookie-write", headers={"Origin": "https://frontend.example.com"})
        self.assertEqual(response.status_code, 403)
        response = await self.client.post("/cookie-write", headers={"Origin": ORIGIN})
        self.assertEqual(response.status_code, 200)

    async def test_statuses_and_unexpected_500(self):
        cases = [("/ok", 200), ("/status/401", 401), ("/status/403", 403),
                 ("/missing", 404), ("/ok?delay=bad", 422), ("/failure", 500)]
        for path, status in cases:
            with self.subTest(path=path), self.assertLogs(LOGGER, logging.INFO) as logs:
                response = await self.client.get(path, headers={"Origin": ORIGIN})
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.headers["access-control-allow-origin"], ORIGIN)
            self.assertGreaterEqual(float(response.headers["x-process-time"]), 0)
            self.assertIn("X-Process-Time", response.headers["access-control-expose-headers"])
            self.assertEqual(len(logs.records), 1)
            self.assertIn(f"status={status}", logs.output[0])
            self.assertNotIn("SECRET_EXCEPTION_CONTENT", response.text + str(logs.output))

    async def test_sensitive_data_not_logged_and_body_unchanged(self):
        payload = {"password": "BODY_SECRET"}
        with self.assertLogs(LOGGER, logging.INFO) as logs:
            response = await self.client.post("/echo?token=QUERY_SECRET", json=payload, headers={
                "Authorization": "Bearer TOKEN_SECRET", "Cookie": "access_token=COOKIE_SECRET",
            })
        self.assertEqual(response.json(), payload)
        for secret in ["BODY_SECRET", "QUERY_SECRET", "TOKEN_SECRET", "COOKIE_SECRET"]:
            self.assertNotIn(secret, str(logs.output))

    async def test_time_header_and_parallel_requests(self):
        with patch("shared.core.http_middleware.perf_counter", side_effect=[10, 10.125]):
            with self.assertLogs(LOGGER, logging.INFO) as logs:
                response = await self.client.get("/ok")
        self.assertEqual(response.headers["x-process-time"], "0.125000")
        self.assertIn("duration_ms=125.000", logs.output[0])
        with self.assertLogs(LOGGER, logging.INFO) as logs:
            responses = await asyncio.gather(*[self.client.get(f"/ok?delay={n / 1000}") for n in range(8)])
        self.assertEqual(len(logs.records), 8)
        self.assertTrue(all(r.status_code == 200 and float(r.headers["x-process-time"]) >= 0 for r in responses))

    async def test_streaming(self):
        with self.assertLogs(LOGGER, logging.INFO) as logs:
            response = await self.client.get("/stream")
        self.assertEqual(response.content, b"firstsecond")
        self.assertEqual(len(logs.records), 1)

    async def test_websocket_passthrough(self):
        incoming = [{"type": "websocket.connect"}, {"type": "websocket.receive", "text": "hello"}]
        sent = []

        async def receive():
            return incoming.pop(0)

        async def send(message):
            sent.append(message)

        scope = {"type": "websocket", "path": "/ws", "headers": [], "query_string": b"",
                 "scheme": "ws", "root_path": "", "subprotocols": []}
        with self.assertNoLogs(LOGGER, logging.INFO):
            await self.app(scope, receive, send)
        self.assertEqual([m["type"] for m in sent], ["websocket.accept", "websocket.send", "websocket.close"])
        self.assertEqual(sent[1]["text"], "hello")

    async def test_exception_after_headers_keeps_actual_status(self):
        async def broken_stream(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            raise RuntimeError("SECRET_STREAM_ERROR")

        async def ignore(*args):
            pass

        with self.assertLogs(LOGGER, logging.ERROR) as logs, self.assertRaises(RuntimeError):
            await RequestLoggingMiddleware(broken_stream)(
                {"type": "http", "method": "GET", "path": "/stream\nforged"}, ignore, ignore,
            )
        self.assertIn("status=200", logs.output[0])
        self.assertIn("failed=true", logs.output[0])
        self.assertNotIn("\n", logs.output[0])
        self.assertNotIn("SECRET_STREAM_ERROR", logs.output[0])

    async def test_real_main_without_database_or_lifespan(self):
        import main
        from database import engine

        with patch.object(engine.sync_engine.dialect, "connect", side_effect=AssertionError("DB access forbidden")):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url=ORIGIN) as client:
                for path, status in [("/health", 200), ("/login", 200), ("/v1/users/me", 401),
                                     ("/admin", 303), ("/missing", 404), ("/openapi.json", 200)]:
                    response = await client.get(path, headers={"Origin": ORIGIN})
                    self.assertEqual(response.status_code, status, path)
                    self.assertIn("x-process-time", response.headers)
                    self.assertEqual(response.headers["access-control-allow-origin"], ORIGIN)


if __name__ == "__main__":
    unittest.main(verbosity=2)

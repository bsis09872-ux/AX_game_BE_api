"""HTTP 요청 결과와 처리 시간을 기록한다. 본문과 인증 정보는 읽지 않는다."""

import json
import logging
from time import perf_counter

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # WebSocket 메시지와 앱 시작/종료는 HTTP 로깅 대상이 아니다.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started_at = perf_counter()
        status_code = 500
        response_seconds = None
        failed = False

        async def send_response(message: Message) -> None:
            nonlocal status_code, response_seconds

            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_seconds = perf_counter() - started_at
                headers = MutableHeaders(scope=message)
                headers["X-Process-Time"] = f"{response_seconds:.6f}"

            # 본문을 모으거나 소비하지 않으므로 스트리밍도 그대로 전달한다.
            await send(message)

        try:
            await self.app(scope, receive, send_response)
        except BaseException:
            # 원래 오류와 취소를 그대로 전달하고 요청 결과만 한 번 기록한다.
            failed = True
            raise
        finally:
            elapsed = response_seconds
            if elapsed is None:
                elapsed = perf_counter() - started_at

            # 경로의 개행/따옴표를 이스케이프하고 query string은 제외한다.
            level = logging.ERROR if failed or status_code >= 500 else logging.INFO
            logger.log(
                level,
                "http_request method=%s path=%s status=%s duration_ms=%.3f failed=%s",
                json.dumps(scope["method"]),
                json.dumps(scope["path"], ensure_ascii=True),
                status_code,
                elapsed * 1000,
                str(failed).lower(),
            )

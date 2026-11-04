"""네트워크 없이 앱을 직접 불러서 응답을 받는 테스트 도우미 (httpx 설치 없이 쓴다)"""

import json

from fastapi import FastAPI


async def call_app(app: FastAPI, path: str = "/", method: str = "GET", query: str = ""):
    """(상태 코드, JSON 본문)을 돌려준다."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query.encode(),
        "headers": [],
        "server": ("test", 80),
        "client": ("test", 1),
    }
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    try:
        await app(scope, receive, send)
    except Exception:
        # 처리하지 못한 오류는 응답을 보낸 뒤 다시 던져진다. 응답은 이미 모아 두었다
        pass
    status = sent[0]["status"]
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, json.loads(body)

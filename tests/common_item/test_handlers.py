"""예외 핸들러 테스트 (by claude)"""

import json
import unittest

from fastapi import FastAPI, Request

from common_item.exceptions import (
    AppError,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    RuleError,
)
from common_item.handlers import (
    app_error_handler,
    register_domain_errors,
    register_exception_handlers,
)


def 가짜_요청() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""})


async def 앱_호출(app: FastAPI, path: str = "/"):
    """네트워크 없이 앱을 직접 불러서 (상태 코드, JSON 본문)을 돌려받는다."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "server": ("test", 80),
        "client": ("test", 1),
    }
    보낸_것 = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(메시지):
        보낸_것.append(메시지)

    await app(scope, receive, send)
    상태 = 보낸_것[0]["status"]
    본문 = b"".join(m.get("body", b"") for m in 보낸_것 if m["type"] == "http.response.body")
    return 상태, json.loads(본문)


class 소유자아님(ValueError):
    """테스트용 도메인 예외. 도메인은 우리 예외를 모르고 ValueError만 던진다."""


class 이미등록됨(ValueError):
    pass


class 핸들러_테스트(unittest.IsolatedAsyncioTestCase):
    async def test_우리_예외는_상태코드와_detail_본문으로_바뀐다(self):
        응답 = await app_error_handler(가짜_요청(), NotFoundError())
        self.assertEqual(응답.status_code, 404)
        self.assertEqual(
            json.loads(응답.body),
            {"detail": {"code": "NOT_FOUND", "message": "요청한 대상을 찾을 수 없습니다."}},
        )

    async def test_params와_바꾼_코드가_본문에_들어간다(self):
        오류 = RateLimitedError("너무 빠릅니다.", code="FISHING_COOLDOWN", params={"retry_after_seconds": 6})
        응답 = await app_error_handler(가짜_요청(), 오류)
        self.assertEqual(응답.status_code, 429)
        self.assertEqual(
            json.loads(응답.body)["detail"],
            {"code": "FISHING_COOLDOWN", "message": "너무 빠릅니다.", "params": {"retry_after_seconds": 6}},
        )

    async def test_부모_예외를_그대로_던지면_500이다(self):
        응답 = await app_error_handler(가짜_요청(), AppError())
        self.assertEqual(응답.status_code, 500)
        self.assertEqual(json.loads(응답.body)["detail"]["code"], "INTERNAL_ERROR")


class 등록_테스트(unittest.IsolatedAsyncioTestCase):
    def test_공통_핸들러를_등록하면_AppError가_들어간다(self):
        앱 = FastAPI()
        register_exception_handlers(앱)
        self.assertIn(AppError, 앱.exception_handlers)

    def test_대응표의_도메인_예외가_하나씩_등록된다(self):
        앱 = FastAPI()
        register_domain_errors(
            앱,
            {
                소유자아님: (ForbiddenError, "NOT_OWNER"),
                이미등록됨: (RuleError, "ITEM_STATE_CONFLICT"),
            },
        )
        self.assertIn(소유자아님, 앱.exception_handlers)
        self.assertIn(이미등록됨, 앱.exception_handlers)

    async def test_도메인_예외가_대응표대로_바뀐다(self):
        앱 = FastAPI()
        register_domain_errors(앱, {소유자아님: (ForbiddenError, "NOT_OWNER")})
        핸들러 = 앱.exception_handlers[소유자아님]
        응답 = await 핸들러(가짜_요청(), 소유자아님("남의 아이템입니다."))
        self.assertEqual(응답.status_code, 403)
        self.assertEqual(
            json.loads(응답.body)["detail"],
            {"code": "NOT_OWNER", "message": "남의 아이템입니다."},
        )

    async def test_도메인_예외에_메시지가_없으면_기본_메시지를_쓴다(self):
        앱 = FastAPI()
        register_domain_errors(앱, {소유자아님: (ForbiddenError, "NOT_OWNER")})
        응답 = await 앱.exception_handlers[소유자아님](가짜_요청(), 소유자아님())
        self.assertEqual(json.loads(응답.body)["detail"]["message"], ForbiddenError.message)


class 실제_앱_테스트(unittest.IsolatedAsyncioTestCase):
    def 앱_만들기(self) -> FastAPI:
        class 아이템없음(NotFoundError):
            code = "ITEM_NOT_FOUND"
            message = "아이템을 찾을 수 없습니다."

        앱 = FastAPI()
        register_exception_handlers(앱)
        register_domain_errors(앱, {소유자아님: (ForbiddenError, "NOT_OWNER")})

        @앱.get("/없음")
        async def 없음():
            raise 아이템없음()

        @앱.get("/남의것")
        async def 남의것():
            raise 소유자아님("남의 아이템입니다.")

        @앱.get("/정상")
        async def 정상():
            return {"ok": True}

        return 앱

    async def test_우리_예외를_던지면_JSON_응답이_된다(self):
        상태, 본문 = await 앱_호출(self.앱_만들기(), "/없음")
        self.assertEqual(상태, 404)
        self.assertEqual(
            본문, {"detail": {"code": "ITEM_NOT_FOUND", "message": "아이템을 찾을 수 없습니다."}}
        )

    async def test_도메인_예외를_던지면_대응표대로_JSON_응답이_된다(self):
        상태, 본문 = await 앱_호출(self.앱_만들기(), "/남의것")
        self.assertEqual(상태, 403)
        self.assertEqual(
            본문, {"detail": {"code": "NOT_OWNER", "message": "남의 아이템입니다."}}
        )

    async def test_정상_요청은_그대로_통과한다(self):
        상태, 본문 = await 앱_호출(self.앱_만들기(), "/정상")
        self.assertEqual(상태, 200)
        self.assertEqual(본문, {"ok": True})


if __name__ == "__main__":
    unittest.main()

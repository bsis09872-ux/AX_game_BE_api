"""프레임워크 예외 핸들러 테스트 (by claude)"""

import json
import unittest

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from common_item.exceptions import ValidationFailedError
from common_item.handlers import register_exception_handlers
from common_item.responses import PageParams


async def 앱_호출(app: FastAPI, path: str = "/", method: str = "GET", query: str = ""):
    """네트워크 없이 앱을 직접 불러서 (상태 코드, JSON 본문, 응답 헤더)를 돌려받는다."""
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
    보낸_것 = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(메시지):
        보낸_것.append(메시지)

    try:
        await app(scope, receive, send)
    except Exception:
        # 처리하지 못한 오류는 응답을 보낸 뒤 서버 쪽에 다시 던져진다. 응답은 이미 모아 두었다
        pass
    상태 = 보낸_것[0]["status"]
    헤더 = {k.decode(): v.decode() for k, v in 보낸_것[0]["headers"]}
    본문 = b"".join(m.get("body", b"") for m in 보낸_것 if m["type"] == "http.response.body")
    return 상태, json.loads(본문), 헤더


class 입력(BaseModel):
    이름: str


def 앱_만들기() -> FastAPI:
    앱 = FastAPI()
    register_exception_handlers(앱)

    @앱.get("/목록")
    async def 목록(파라미터: PageParams = Depends()):
        return {"offset": 파라미터.offset}

    @앱.get("/아이템/{item_id}")
    async def 아이템(item_id: int):
        return {"item_id": item_id}

    @앱.post("/만들기")
    async def 만들기(내용: 입력):
        return {"ok": True}

    @앱.get("/직접")
    async def 직접():
        raise HTTPException(status_code=403, detail={"code": "MY_CODE", "message": "직접 만든 오류입니다."})

    @앱.get("/글자")
    async def 글자():
        raise HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})

    @앱.get("/터짐")
    async def 터짐():
        raise RuntimeError("비밀 내부 정보 boom")

    return 앱


# 결정(11/03): 요청 값 검증 실패(422)는 틀린 필드 이름(params.fields)을 담지 않고,
# 우리가 정한 코드와 메시지만 준다. 그래서 아래 테스트는 항상 같은 본문을 기대한다.
기본_422_본문 = ValidationFailedError().to_body()


class 요청값_검증_테스트(unittest.IsolatedAsyncioTestCase):
    async def test_쿼리가_범위를_벗어나면_422이다(self):
        상태, 본문, _ = await 앱_호출(앱_만들기(), "/목록", query="size=500")
        self.assertEqual(상태, 422)
        self.assertEqual(본문, 기본_422_본문)
        self.assertEqual(본문["detail"]["code"], "VALIDATION_ERROR")

    async def test_경로_값의_타입이_틀리면_422이다(self):
        상태, 본문, _ = await 앱_호출(앱_만들기(), "/아이템/abc")
        self.assertEqual(상태, 422)
        self.assertEqual(본문, 기본_422_본문)

    async def test_여러_값이_틀려도_같은_본문이다(self):
        상태, 본문, _ = await 앱_호출(앱_만들기(), "/목록", query="page=0&size=500")
        self.assertEqual(상태, 422)
        self.assertEqual(본문, 기본_422_본문)

    async def test_본문이_없으면_422이다(self):
        상태, 본문, _ = await 앱_호출(앱_만들기(), "/만들기", method="POST")
        self.assertEqual(상태, 422)
        self.assertEqual(본문, 기본_422_본문)

    async def test_입력값과_필드_이름은_응답에_나오지_않는다(self):
        _, 본문, _ = await 앱_호출(앱_만들기(), "/목록", query="size=500")
        self.assertNotIn("params", 본문["detail"])
        self.assertNotIn("500", json.dumps(본문))

    async def test_정상_범위는_그대로_통과한다(self):
        상태, 본문, _ = await 앱_호출(앱_만들기(), "/목록", query="page=2&size=10")
        self.assertEqual(상태, 200)
        self.assertEqual(본문, {"offset": 10})


class HTTP오류_테스트(unittest.IsolatedAsyncioTestCase):
    async def test_없는_경로는_404_NOT_FOUND이다(self):
        상태, 본문, _ = await 앱_호출(앱_만들기(), "/없는경로")
        self.assertEqual(상태, 404)
        self.assertEqual(
            본문, {"detail": {"code": "NOT_FOUND", "message": "요청한 대상을 찾을 수 없습니다."}}
        )

    async def test_허용되지_않은_메서드는_405이다(self):
        상태, 본문, _ = await 앱_호출(앱_만들기(), "/목록", method="DELETE")
        self.assertEqual(상태, 405)
        self.assertEqual(본문["detail"]["code"], "METHOD_NOT_ALLOWED")

    async def test_detail에_code와_message_객체를_넣으면_그대로_쓴다(self):
        상태, 본문, _ = await 앱_호출(앱_만들기(), "/직접")
        self.assertEqual(상태, 403)
        self.assertEqual(본문, {"detail": {"code": "MY_CODE", "message": "직접 만든 오류입니다."}})

    async def test_글자_detail은_우리_기본_메시지로_바뀌고_헤더는_유지된다(self):
        상태, 본문, 헤더 = await 앱_호출(앱_만들기(), "/글자")
        self.assertEqual(상태, 401)
        self.assertEqual(본문["detail"]["code"], "UNAUTHORIZED")
        self.assertNotIn("Not authenticated", json.dumps(본문))
        self.assertEqual(헤더["www-authenticate"], "Bearer")


class 처리하지_못한_오류_테스트(unittest.IsolatedAsyncioTestCase):
    async def test_예상_못_한_오류는_500_INTERNAL_ERROR이다(self):
        상태, 본문, _ = await 앱_호출(앱_만들기(), "/터짐")
        self.assertEqual(상태, 500)
        self.assertEqual(본문["detail"]["code"], "INTERNAL_ERROR")

    async def test_내부_정보는_응답에_나오지_않는다(self):
        _, 본문, _ = await 앱_호출(앱_만들기(), "/터짐")
        글 = json.dumps(본문, ensure_ascii=False)
        self.assertNotIn("boom", 글)
        self.assertNotIn("비밀", 글)


class 등록_테스트(unittest.TestCase):
    def test_세_종류의_프레임워크_예외가_등록된다(self):
        앱 = FastAPI()
        register_exception_handlers(앱)
        self.assertIn(RequestValidationError, 앱.exception_handlers)
        self.assertIn(StarletteHTTPException, 앱.exception_handlers)
        self.assertIn(Exception, 앱.exception_handlers)


if __name__ == "__main__":
    unittest.main()

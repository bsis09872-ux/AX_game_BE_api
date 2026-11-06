"""공통 로깅 테스트"""

import io
import logging
import unittest

from fastapi import FastAPI

from common_study.app_logging import get_logger, register_request_logging, setup_logging
from common_study.handlers import register_exception_handlers
from tests.test_framework_errors import 앱_호출


class 모아두는_핸들러(logging.Handler):
    """남겨진 기록을 리스트에 모아 두는 테스트용 핸들러."""

    def __init__(self):
        super().__init__()
        self.기록 = []

    def emit(self, record):
        self.기록.append(record)


def 앱_로거_복원_예약(테스트):
    """테스트가 끝나면 "app" 로거를 원래 상태로 되돌린다(다른 테스트에 영향이 없게)."""
    로거 = logging.getLogger("app")
    핸들러들, 레벨, 전파 = list(로거.handlers), 로거.level, 로거.propagate

    def 복원():
        로거.handlers[:] = 핸들러들
        로거.setLevel(레벨)
        로거.propagate = 전파

    테스트.addCleanup(복원)


class 로거_이름_테스트(unittest.TestCase):
    def test_이름_앞에_app이_붙는다(self):
        self.assertEqual(get_logger("x").name, "app.x")

    def test_app_로거_밑에_있어서_함께_설정된다(self):
        앱_로거 = logging.getLogger("app")
        self.assertIs(get_logger("x").parent, 앱_로거)


class 설정_테스트(unittest.TestCase):
    def setUp(self):
        앱_로거_복원_예약(self)

    def test_여러_번_불러도_핸들러는_하나만_늘어난다(self):
        전 = len(logging.getLogger("app").handlers)
        setup_logging()
        setup_logging()
        self.assertEqual(len(logging.getLogger("app").handlers), 전 + 1)

    def test_핸들러를_바꿔_끼울_수_있다(self):
        첫째, 둘째 = 모아두는_핸들러(), 모아두는_핸들러()
        setup_logging(handler=첫째)
        get_logger("t").info("하나")
        setup_logging(handler=둘째)
        get_logger("t").info("둘")
        self.assertEqual(len(첫째.기록), 1)
        self.assertEqual(len(둘째.기록), 1)

    def test_정한_레벨보다_낮은_기록은_버린다(self):
        핸들러 = 모아두는_핸들러()
        setup_logging(level=logging.WARNING, handler=핸들러)
        get_logger("t").info("버려짐")
        get_logger("t").warning("남음")
        self.assertEqual(len(핸들러.기록), 1)

    def test_기록_형식에_레벨과_파일_줄번호가_있다(self):
        출력 = io.StringIO()
        setup_logging(handler=logging.StreamHandler(출력))
        get_logger("fmt").error("문제 발생")
        글 = 출력.getvalue()
        self.assertIn("ERROR", 글)
        self.assertIn("test_app_logging.py:", 글)
        self.assertIn("문제 발생", 글)


def 앱_만들기() -> FastAPI:
    앱 = FastAPI()
    register_exception_handlers(앱)
    register_request_logging(앱)

    @앱.get("/ok")
    async def ok():
        return {"ok": True}

    @앱.get("/터짐")
    async def 터짐():
        raise RuntimeError("비밀 내부 정보 boom")

    return 앱


class 요청_기록_테스트(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        앱_로거_복원_예약(self)

    async def test_요청_한_줄이_남는다(self):
        with self.assertLogs("app", level="INFO") as 캡처:
            await 앱_호출(앱_만들기(), "/ok")
        글 = "\n".join(캡처.output)
        for 조각 in ("GET", "/ok", "200"):
            self.assertIn(조각, 글)

    async def test_없는_경로도_상태_코드와_함께_남는다(self):
        with self.assertLogs("app", level="INFO") as 캡처:
            await 앱_호출(앱_만들기(), "/없는경로")
        self.assertIn("404", "\n".join(캡처.output))

    async def test_쿼리_문자열은_남기지_않는다(self):
        with self.assertLogs("app", level="INFO") as 캡처:
            await 앱_호출(앱_만들기(), "/ok", query="token=secret")
        self.assertNotIn("secret", "\n".join(캡처.output))


class 오류_기록_테스트(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        앱_로거_복원_예약(self)

    async def test_처리하지_못한_오류는_ERROR와_오류_내용으로_남는다(self):
        with self.assertLogs("app", level="ERROR") as 캡처:
            await 앱_호출(앱_만들기(), "/터짐")
        기록 = 캡처.records[0]
        self.assertEqual(기록.levelno, logging.ERROR)
        self.assertIn("/터짐", 기록.getMessage())
        self.assertIsInstance(기록.exc_info[1], RuntimeError)

    async def test_로그에는_남겨도_응답에는_내부_정보가_없다(self):
        with self.assertLogs("app", level="ERROR"):
            상태, 본문, _ = await 앱_호출(앱_만들기(), "/터짐")
        self.assertEqual(상태, 500)
        self.assertNotIn("boom", str(본문))


if __name__ == "__main__":
    unittest.main()

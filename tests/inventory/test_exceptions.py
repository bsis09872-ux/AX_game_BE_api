"""도메인 계층 예외 테스트: 부모 분류, 에러 코드, 기본 메시지, 팀 공통 핸들러와의 연결"""

import unittest

from fastapi import FastAPI

from inventory.domain.exceptions import (
    DefinitionImmutableFieldError,
    DefinitionNotFoundError,
    InvalidStateError,
    ItemNotFoundError,
    ItemRuleViolationError,
    ResaleNotAvailableError,
)
from shared.core.exception_handlers import register_exception_handlers
from shared.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from tests.inventory.asgi_client import call_app

# (예외, 부모 분류, 에러 코드, 팀 핸들러가 정하는 상태 코드)
# NotOwnerError(403)는 팀 공통에 ForbiddenError가 생긴 뒤 U03에서 만들고 이 표에 넣는다
EXPECTED = [
    (ItemRuleViolationError, BusinessRuleError, "ITEM_RULE_VIOLATION", 400),
    (DefinitionImmutableFieldError, BusinessRuleError, "DEFINITION_IMMUTABLE", 400),
    (ResaleNotAvailableError, BusinessRuleError, "RESALE_NOT_AVAILABLE", 400),
    (InvalidStateError, ConflictError, "ITEM_STATE_CONFLICT", 409),
    (ItemNotFoundError, NotFoundError, "ITEM_NOT_FOUND", 404),
    (DefinitionNotFoundError, NotFoundError, "DEFINITION_NOT_FOUND", 404),
]


class ExceptionDefinitionTest(unittest.TestCase):
    def test_parent_and_code_match_the_design(self):
        for exception_class, parent, code, _ in EXPECTED:
            with self.subTest(exception=exception_class.__name__):
                self.assertTrue(issubclass(exception_class, parent))
                self.assertEqual(exception_class.code, code)

    def test_codes_are_unique_and_upper_snake_case(self):
        codes = [row[0].code for row in EXPECTED]
        self.assertEqual(len(codes), len(set(codes)))
        for code in codes:
            with self.subTest(code=code):
                self.assertRegex(code, r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$")

    def test_each_exception_has_its_own_default_message(self):
        for exception_class, parent, _, _ in EXPECTED:
            with self.subTest(exception=exception_class.__name__):
                self.assertTrue(exception_class.message)
                self.assertNotEqual(exception_class.message, parent.message)

    def test_message_can_be_overridden(self):
        error = InvalidStateError("이미 판매 대기 중입니다.")
        self.assertEqual(error.message, "이미 판매 대기 중입니다.")
        self.assertEqual(str(error), "이미 판매 대기 중입니다.")
        self.assertEqual(error.code, "ITEM_STATE_CONFLICT")

    def test_default_message_is_used_when_not_given(self):
        error = ItemNotFoundError()
        self.assertEqual(error.message, ItemNotFoundError.message)
        self.assertEqual(str(error), ItemNotFoundError.message)


def make_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    for index, (exception_class, _, _, _) in enumerate(EXPECTED):
        # 반복문의 값이 늦게 바뀌지 않도록 기본 인자로 고정한다
        async def raise_it(exception_class=exception_class):
            raise exception_class()

        app.add_api_route(f"/raise/{index}", raise_it, methods=["GET"])
    return app


class TeamHandlerIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_team_handler_turns_each_exception_into_the_expected_response(self):
        app = make_app()
        for index, (exception_class, _, code, status_code) in enumerate(EXPECTED):
            with self.subTest(exception=exception_class.__name__):
                status, body = await call_app(app, f"/raise/{index}")
                self.assertEqual(status, status_code)
                self.assertEqual(
                    body,
                    {"detail": {"code": code, "message": exception_class.message}},
                )


if __name__ == "__main__":
    unittest.main()

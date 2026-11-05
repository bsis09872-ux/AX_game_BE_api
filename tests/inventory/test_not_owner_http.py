"""NotOwnerError가 팀 공통 핸들러에서 403으로 나가는지 확인하는 테스트 (D20)

팀 공통(shared.core)에 ForbiddenError와 403 분기가 아직 없으면 이 테스트는 건너뛴다.
둘이 생기면 자동으로 켜지고, 그때 NotOwnerError의 부모가 ForbiddenError가 아니면 실패해서
"부모를 바꿔라"는 알림이 된다.
"""

import unittest

from fastapi import FastAPI

from inventory.domain.exceptions import NotOwnerError
from shared.core import exceptions as shared_exceptions
from shared.core.exception_handlers import register_exception_handlers
from tests.inventory.asgi_client import call_app

ForbiddenError = getattr(shared_exceptions, "ForbiddenError", None)


@unittest.skipIf(ForbiddenError is None, "팀 공통에 ForbiddenError가 아직 없다 (D20)")
class NotOwnerHttpTest(unittest.IsolatedAsyncioTestCase):
    def test_not_owner_error_is_a_forbidden_error(self):
        self.assertTrue(issubclass(NotOwnerError, ForbiddenError))

    async def test_team_handler_returns_403_with_the_error_body(self):
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/not-owner")
        async def not_owner():
            raise NotOwnerError()

        status, body = await call_app(app, "/not-owner")
        self.assertEqual(status, 403)
        self.assertEqual(
            body,
            {"detail": {"code": "NOT_OWNER", "message": NotOwnerError.message}},
        )


if __name__ == "__main__":
    unittest.main()

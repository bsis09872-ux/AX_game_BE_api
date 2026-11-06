import asyncio
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
TEST_URL = os.environ.get("AUTH_TEST_DATABASE_URL")

if TEST_URL:
    # run_auth_integration.py가 만든 임시 DB만 사용한다.
    if not TEST_URL.startswith("postgresql+asyncpg://") or not TEST_URL.endswith("/auth_test"):
        raise RuntimeError("통합 테스트는 auth_test DB에서만 실행할 수 있습니다.")
    os.environ["DATABASE_URL"] = TEST_URL
    from sqlalchemy import func, select, text
    from sqlalchemy.ext.asyncio import AsyncSession
    from auth.infrastructure.models import RevokedTokenModel
    from auth.infrastructure.password_hasher import PasslibPasswordHasher
    from database import AsyncSessionLocal, Base, engine
    from main import app
    from users.infrastructure.models import UserModel
    from users.infrastructure.repositories import SqlAlchemyUserRepository


async def request(method, path, body=None, token=None, form=False, application=None, query_string=b""):
    data = (urlencode(body) if form else json.dumps(body)).encode() if body is not None else b""
    headers = [(b"content-type", b"application/x-www-form-urlencoded" if form else b"application/json")]
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode()))
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
        "root_path": "", "query_string": query_string, "headers": headers,
        "client": ("127.0.0.1", 12345), "server": ("test", 80),
    }
    messages = []

    async def receive():
        return {"type": "http.request", "body": data, "more_body": False}

    async def send(message):
        messages.append(message)

    try:
        await (application if application is not None else app)(scope, receive, send)
    except Exception:
        # ServerErrorMiddleware는 500 응답 전송 후 원래 예외를 다시 발생시킨다.
        if not any(m.get("status") == 500 for m in messages):
            raise
    start = next(m for m in messages if m["type"] == "http.response.start")
    raw = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return start["status"], json.loads(raw) if raw else None, dict(start["headers"])


@unittest.skipUnless(TEST_URL, "tests/run_auth_integration.py로 임시 DB를 준비하세요")
class AuthIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.login_id = "test_" + uuid4().hex[:16]
        self.password = "password-for-auth-test"
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await engine.dispose()

    async def register(self):
        return await request("POST", "/v1/auth/register", {
            "login_id": self.login_id, "display_name": "코코", "password": self.password,
        })

    async def login(self, password=None):
        return await request("POST", "/v1/auth/token", {
            "username": self.login_id, "password": password or self.password,
        }, form=True)

    async def test_signup_login_me_and_idempotent_logout(self):
        status, created, _ = await self.register()
        self.assertEqual(status, 201)
        self.assertEqual(set(created), {"id", "login_id", "created_at"})
        self.assertTrue(created["id"].isdigit())
        self.assertTrue(created["created_at"].endswith("Z"))
        # 다른 세션에서도 조회되어야 응답 전에 가입이 commit된 것이다.
        async with AsyncSessionLocal() as session:
            user = await session.get(UserModel, int(created["id"]))
            self.assertEqual(user.role, "USER")
            self.assertNotEqual(user.password_hash, self.password)
            self.assertTrue(await PasslibPasswordHasher().verify(self.password, user.password_hash))
        status, issued, headers = await self.login()
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"cache-control"], b"no-store")
        self.assertEqual(issued["token_type"], "bearer")
        token = issued["access_token"]
        _, other, _ = await self.login()
        status, me, _ = await request("GET", "/v1/users/me", token=token)
        self.assertEqual(status, 200)
        self.assertEqual(me["id"], created["id"])
        self.assertEqual(set(me), {"id", "login_id", "created_at", "display_name", "role"})
        results = await asyncio.gather(*[
            request("POST", "/v1/auth/logout", token=token) for _ in range(2)
        ])
        self.assertEqual([r[0] for r in results], [204, 204])
        self.assertTrue(all(r[1] is None for r in results))
        status, error, _ = await request("GET", "/v1/users/me", token=token)
        self.assertEqual(status, 401)
        self.assertEqual(error["detail"]["code"], "INVALID_TOKEN")
        self.assertEqual((await request("GET", "/v1/users/me", token=other["access_token"]))[0], 200)
        async with AsyncSessionLocal() as session:
            count = await session.scalar(select(func.count()).select_from(RevokedTokenModel).where(
                RevokedTokenModel.user_id == int(created["id"])
            ))
            self.assertEqual(count, 1)

    async def test_missing_malformed_and_expired_tokens(self):
        import jwt
        from auth.infrastructure.token_codec import get_token_codec
        from datetime import datetime, timezone

        for token in (None, "not-a-jwt"):
            status, _, headers = await request("GET", "/v1/users/me", token=token)
            self.assertEqual(status, 401)
            self.assertEqual(headers[b"www-authenticate"], b"Bearer")
        issued = get_token_codec().issue(1)
        payload = jwt.decode(issued.access_token, options={"verify_signature": False})
        now = int(datetime.now(timezone.utc).timestamp())
        payload.update(iat=now - 120, exp=now - 60)
        expired = jwt.encode(payload, os.environ["JWT_SECRET_KEY"], algorithm="HS256")
        self.assertEqual((await request("GET", "/v1/users/me", token=expired))[0], 401)
        self.assertEqual((await request("POST", "/v1/auth/logout", token=expired))[0], 401)

    async def test_me_uses_authenticated_id_not_query_parameter(self):
        _, created, _ = await self.register()
        _, issued, _ = await self.login()
        status, me, _ = await request(
            "GET", "/v1/users/me", token=issued["access_token"],
            query_string=b"user_id=9223372036854775807",
        )
        self.assertEqual(status, 200)
        self.assertEqual(me["id"], created["id"])
        self.assertEqual((await request(
            "GET", "/v1/users/me", query_string=f"user_id={created['id']}".encode(),
        ))[0], 401)

    async def test_user_router_accepts_an_independent_identity_provider(self):
        from fastapi import FastAPI
        from users.presentation.router import create_user_router

        _, created, _ = await self.register()

        async def current_user_id() -> int:
            return int(created["id"])

        isolated_app = FastAPI()
        isolated_app.include_router(create_user_router(current_user_id), prefix="/v1")
        status, me, headers = await request("GET", "/v1/users/me", application=isolated_app)
        self.assertEqual(status, 200)
        self.assertEqual(me["id"], created["id"])
        self.assertEqual(headers[b"cache-control"], b"no-store")
        operation = isolated_app.openapi()["paths"]["/v1/users/me"]["get"]
        self.assertNotIn("security", operation)
        self.assertNotIn("parameters", operation)

    async def test_wrong_password_unknown_and_deleted_account(self):
        from datetime import datetime, timezone

        unknown = await self.login()
        await self.register()
        wrong = await self.login("wrong-password")
        _, issued, _ = await self.login()
        async with AsyncSessionLocal() as session:
            user = await session.scalar(select(UserModel).where(UserModel.login_id == self.login_id))
            user.deleted_at = datetime.now(timezone.utc)
            await session.commit()
        inactive = await self.login()
        self.assertEqual([unknown[0], wrong[0], inactive[0]], [401, 401, 401])
        self.assertEqual(unknown[1], wrong[1])
        self.assertEqual(wrong[1], inactive[1])
        self.assertEqual((await request("GET", "/v1/users/me", token=issued["access_token"]))[0], 401)

    async def test_duplicate_signup_race_uses_actual_constraint(self):
        async with AsyncSessionLocal() as session:
            constraints = await session.scalars(text(
                "SELECT conname FROM pg_constraint WHERE conrelid = 'users'::regclass AND contype = 'u'"
            ))
            self.assertIn("users_login_id_key", constraints.all())
        original = SqlAlchemyUserRepository.find_by_login_id
        barrier = asyncio.Barrier(2)

        async def find(repository, login_id):
            result = await original(repository, login_id)
            # 양쪽 사전 조회가 모두 None을 확인한 뒤 INSERT로 진행시킨다.
            await asyncio.wait_for(barrier.wait(), timeout=10)
            return result

        with patch.object(SqlAlchemyUserRepository, "find_by_login_id", find):
            results = await asyncio.gather(self.register(), self.register())
        self.assertEqual(sorted(r[0] for r in results), [201, 409])
        conflict = next(r for r in results if r[0] == 409)
        self.assertEqual(conflict[1]["detail"]["code"], "LOGIN_ID_ALREADY_EXISTS")
        async with AsyncSessionLocal() as session:
            count = await session.scalar(select(func.count()).select_from(UserModel).where(
                UserModel.login_id == self.login_id
            ))
            self.assertEqual(count, 1)
        self.assertEqual((await self.register())[0], 409)

    async def test_commit_failure_rolls_back_and_does_not_return_success(self):
        async def fail_commit(session):
            raise RuntimeError("simulated storage failure")

        with patch.object(AsyncSession, "commit", fail_commit):
            status, body, _ = await self.register()
        self.assertEqual(status, 500)
        self.assertEqual(body["detail"]["code"], "INTERNAL_SERVER_ERROR")
        async with AsyncSessionLocal() as session:
            user = await session.scalar(select(UserModel).where(UserModel.login_id == self.login_id))
            self.assertIsNone(user)

    async def test_input_validation_does_not_expose_password_or_allow_role(self):
        for changes in (
            {"display_name": "   "}, {"display_name": "x" * 51},
            {"role": "ADMIN"}, {"login_id": "Bad ID"}, {"password": "x" * 1025},
        ):
            payload = {"login_id": self.login_id, "display_name": "코코", "password": self.password}
            payload.update(changes)
            status, error, _ = await request("POST", "/v1/auth/register", payload)
            self.assertEqual(status, 422)
            self.assertTrue(all("input" not in e for e in error["detail"]))
            self.assertNotIn(self.password, json.dumps(error))

    async def test_failed_logout_rolls_back_revocation(self):
        await self.register()
        _, issued, _ = await self.login()
        token = issued["access_token"]

        async def fail_commit(session):
            raise RuntimeError("simulated storage failure")

        with patch.object(AsyncSession, "commit", fail_commit):
            self.assertEqual((await request("POST", "/v1/auth/logout", token=token))[0], 500)
        self.assertEqual((await request("GET", "/v1/users/me", token=token))[0], 200)

    async def test_lifespan_and_openapi_register_all_routes(self):
        async with app.router.lifespan_context(app):
            self.assertEqual((await request("GET", "/health"))[0], 200)
            status, schema, _ = await request("GET", "/openapi.json")
            self.assertEqual(status, 200)
            for path in ("/v1/auth/register", "/v1/auth/token", "/v1/auth/logout", "/v1/users/me"):
                self.assertIn(path, schema["paths"])
            self.assertTrue(schema["paths"]["/v1/users/me"]["get"]["security"])
            flow = schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]["flows"]["password"]
            self.assertEqual(flow["tokenUrl"], "v1/auth/token")


if __name__ == "__main__":
    unittest.main()

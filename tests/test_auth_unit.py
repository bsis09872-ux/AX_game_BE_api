import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import jwt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from auth.application.contracts import AuthUser, CreatedUser
from auth.application.service import AuthService
from auth.domain.exceptions import InvalidCredentialsError, InvalidTokenError
from auth.infrastructure.token_codec import JwtTokenCodec
from users.domain.user import User


class TokenTests(unittest.TestCase):
    def setUp(self):
        self.secret = "unit-test-secret-" * 4
        self.codec = JwtTokenCodec(self.secret, 60)

    def test_round_trip_and_distinct_token_ids(self):
        first = self.codec.issue(42)
        second = self.codec.issue(42)
        self.assertEqual(first.expires_in, 60)
        claims = self.codec.decode(first.access_token)
        self.assertEqual(claims.user_id, 42)
        self.assertNotEqual(claims.jti, self.codec.decode(second.access_token).jti)

    def test_rejects_invalid_claims_signature_and_algorithm(self):
        now = int(datetime.now(timezone.utc).timestamp())
        valid = {
            "sub": "42", "jti": str(uuid4()), "iat": now, "exp": now + 60,
            "iss": "ax-game-be-api", "aud": "ax-game-client", "token_type": "access",
        }
        variants = [
            {**valid, "exp": now - 1}, {**valid, "iat": now + 120},
            {**valid, "sub": "0"}, {**valid, "sub": "9223372036854775808"},
            {**valid, "sub": "abc"}, {**valid, "jti": "bad-uuid"},
            {**valid, "aud": "other"}, {**valid, "iss": "other"},
            {**valid, "token_type": "refresh"}, {**valid, "exp": "invalid"},
            {**valid, "exp": now + 0.5}, {**valid, "iat": True},
        ]
        variants += [{k: v for k, v in valid.items() if k != missing} for missing in valid]
        for payload in variants:
            with self.subTest(payload=payload), self.assertRaises(InvalidTokenError):
                self.codec.decode(jwt.encode(payload, self.secret, algorithm="HS256"))
        for token in (
            "malformed", jwt.encode(valid, "wrong-secret-" * 4, algorithm="HS256"),
            jwt.encode(valid, self.secret, algorithm="HS512"),
        ):
            with self.assertRaises(InvalidTokenError):
                self.codec.decode(token)

    def test_rejects_invalid_configuration(self):
        for secret, ttl in (("short", 60), (self.secret, 0), (self.secret, 86401)):
            with self.assertRaises(ValueError):
                JwtTokenCodec(secret, ttl)


class AuthServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.hasher = AsyncMock()
        self.creator = AsyncMock()
        self.reader = AsyncMock()
        self.codec = Mock()
        self.revoked = AsyncMock()
        self.transaction = AsyncMock()
        self.service = AuthService(
            self.hasher, self.creator, self.reader, self.codec,
            self.revoked, self.transaction,
        )

    async def test_signup_commits_after_creation_and_propagates_commit_failure(self):
        events = []
        created = CreatedUser(1, "coco", datetime.now(timezone.utc))

        async def create(**kwargs):
            events.append("create")
            return created

        async def commit():
            events.append("commit")

        self.creator.create_user.side_effect = create
        self.transaction.commit.side_effect = commit
        result = await self.service.register_user("coco", "코코", "password")
        self.assertIs(result, created)
        self.assertEqual(events, ["create", "commit"])
        self.transaction.commit.side_effect = RuntimeError("commit failed")
        with self.assertRaises(RuntimeError):
            await self.service.register_user("coco", "코코", "password")

    async def test_unknown_wrong_password_and_inactive_accounts_reject_login(self):
        for user, matches in (
            (None, False), (AuthUser(1, True, "hash"), False),
            (AuthUser(1, False, "hash"), True),
        ):
            self.reader.find_by_login_id.return_value = user
            self.hasher.verify.return_value = matches
            with self.assertRaises(InvalidCredentialsError):
                await self.service.login("coco", "password")
        self.codec.issue.assert_not_called()

    async def test_revoked_or_inactive_tokens_cannot_authenticate(self):
        self.revoked.contains.return_value = True
        with self.assertRaises(InvalidTokenError):
            await self.service.authenticate("token")
        self.reader.find_by_id.assert_not_awaited()
        self.revoked.contains.return_value = False
        for user in (None, AuthUser(1, False, "hash")):
            self.reader.find_by_id.return_value = user
            with self.assertRaises(InvalidTokenError):
                await self.service.authenticate("token")


class UserTests(unittest.TestCase):
    def test_auction_boundary_and_timezones(self):
        now = datetime.now(timezone.utc)
        user = User("coco", "hash", display_name="코코")
        self.assertFalse(user.is_auction_blocked(now))
        user.auction_blocked_until = now + timedelta(seconds=1)
        self.assertTrue(user.is_auction_blocked(now))
        self.assertFalse(user.is_auction_blocked(user.auction_blocked_until))
        with self.assertRaises(ValueError):
            user.is_auction_blocked(now.replace(tzinfo=None))
        user.auction_blocked_until = now.replace(tzinfo=None)
        with self.assertRaises(RuntimeError):
            user.is_auction_blocked(now)


if __name__ == "__main__":
    unittest.main()

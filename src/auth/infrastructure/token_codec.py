# JWT 서명과 검증을 담당한다. 알고리즘과 발급자/대상은 서버 설정으로 고정한다.
import os
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from uuid import UUID, uuid4

import jwt

from auth.application.contracts import TokenCodec
from auth.application.dto import IssuedToken, TokenClaims
from auth.domain.exceptions import InvalidTokenError


class JwtTokenCodec(TokenCodec):
    def __init__(self, secret: str, ttl_seconds: int = 1800):
        if len(secret.encode("utf-8")) < 32:
            raise ValueError("JWT_SECRET_KEY는 32바이트 이상의 무작위 값이어야 합니다.")
        if not 60 <= ttl_seconds <= 86400:
            raise ValueError("JWT_TTL_SECONDS는 60~86400 사이여야 합니다.")
        self._secret = secret
        self._ttl_seconds = ttl_seconds
        self._issuer = "ax-game-be-api"
        self._audience = "ax-game-client"

    def issue(self, user_id: int, session_id: UUID | None = None) -> IssuedToken:
        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "sub": str(user_id), "jti": str(uuid4()),
                "iat": now, "exp": now + timedelta(seconds=self._ttl_seconds),
                "iss": self._issuer, "aud": self._audience, "token_type": "access",
                **({"sid": str(session_id)} if session_id is not None else {}),
            },
            self._secret, algorithm="HS256",
        )
        return IssuedToken(access_token=token, expires_in=self._ttl_seconds)

    def decode(self, token: str) -> TokenClaims:
        try:
            payload = jwt.decode(
                token, self._secret, algorithms=["HS256"],
                issuer=self._issuer, audience=self._audience,
                options={"require": ["sub", "jti", "iat", "exp", "iss", "aud", "token_type"]},
            )
            # 서명만으로 DB 식별자와 시간 필드의 형식까지 보장되지는 않는다.
            subject = payload["sub"]
            if not isinstance(subject, str) or re.fullmatch(r"[1-9][0-9]{0,18}", subject) is None:
                raise ValueError("Invalid subject")
            if int(subject) > 2**63 - 1 or payload["token_type"] != "access":
                raise ValueError("Invalid access token")
            if type(payload["iat"]) is not int or type(payload["exp"]) is not int:
                raise ValueError("Invalid token timestamp")
            if payload["exp"] <= payload["iat"]:
                raise ValueError("Invalid token lifetime")
            if not isinstance(payload["jti"], str):
                raise ValueError("Invalid token identifier")
            if "sid" in payload and not isinstance(payload["sid"], str):
                raise ValueError("Invalid session identifier")
            return TokenClaims(
                user_id=int(subject), jti=UUID(payload["jti"]),
                expires_at=datetime.fromtimestamp(payload["exp"], timezone.utc),
                session_id=UUID(payload["sid"]) if "sid" in payload else None,
            )
        except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError, OSError) as exc:
            raise InvalidTokenError() from exc


@lru_cache
def get_token_codec() -> JwtTokenCodec:
    # 기본 비밀키를 두지 않는다. 환경변수 변경은 서버 재시작 후 적용된다.
    return JwtTokenCodec(
        secret=os.environ["JWT_SECRET_KEY"],
        ttl_seconds=int(os.environ.get("JWT_TTL_SECONDS", "1800")),
    )

import hashlib
import re
import secrets

from auth.domain.exceptions import InvalidTokenError


class OpaqueRefreshTokenCodec:
    def generate(self) -> str:
        return secrets.token_urlsafe(48)

    def digest(self, token: str) -> str:
        if not isinstance(token, str) or re.fullmatch(r"[A-Za-z0-9_-]{64}", token) is None:
            raise InvalidTokenError()
        return hashlib.sha256(token.encode("ascii")).hexdigest()

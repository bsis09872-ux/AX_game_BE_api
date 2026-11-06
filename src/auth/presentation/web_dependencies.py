import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from auth.application.contracts import TokenPair
from auth.application.service import AuthService
from auth.domain.exceptions import AuthenticationError
from auth.presentation.dependencies import get_auth_service


@dataclass(frozen=True)
class WebSettings:
    origin: str
    secure: bool


@lru_cache
def get_web_settings() -> WebSettings:
    # 쿠키 인증 POST를 허용할 주소를 고정한다. 요청의 Host를 신뢰해 만들지 않는다.
    origin = os.environ.get("WEB_ORIGIN", "http://127.0.0.1:8000").rstrip("/")
    parsed = urlsplit(origin)

    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError("WEB_ORIGIN에는 웹 서비스의 origin만 지정하세요.")

    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("로컬 개발 이외에는 HTTPS가 필요합니다.")

    return WebSettings(origin, parsed.scheme == "https")


def require_web_origin(request: Request) -> None:
    # 브라우저가 쿠키를 자동 첨부하므로 다른 출처의 POST는 거절한다.
    if request.headers.get("origin") != get_web_settings().origin:
        raise HTTPException(status_code=403, detail="허용되지 않은 요청 출처입니다.")


def set_auth_cookies(response, tokens: TokenPair) -> None:
    # 토큰마다 남은 수명을 적용한다. HttpOnly로 스크립트의 토큰 원문 접근을 막는다.
    for name, value, ttl in (
        ("access_token", tokens.access_token, tokens.expires_in),
        ("refresh_token", tokens.refresh_token, tokens.refresh_expires_in),
    ):
        response.set_cookie(
            name,
            value,
            max_age=ttl,
            path="/",
            httponly=True,
            secure=get_web_settings().secure,
            samesite="lax",
        )

    response.headers["Cache-Control"] = "no-store"


def clear_auth_cookies(response) -> None:
    # 설정할 때와 같은 이름/경로의 쿠키를 만료시킨다. DB 기록을 삭제하는 함수는 아니다.
    for name in ("access_token", "refresh_token"):
        response.delete_cookie(
            name,
            path="/",
            httponly=True,
            secure=get_web_settings().secure,
            samesite="lax",
        )

    response.headers["Cache-Control"] = "no-store"


class WebAuthenticationRequired(Exception):
    pass


async def get_current_web_user_id(
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> int:
    # users에는 인증을 마친 회원 ID만 넘기고 토큰 처리 책임은 auth에 둔다.
    token = request.cookies.get("access_token")

    if not token:
        raise WebAuthenticationRequired()

    try:
        return (await service.authenticate(token)).user_id
    except AuthenticationError as exc:
        raise WebAuthenticationRequired() from exc


def register_web_auth_handlers(app) -> None:
    # 의존성에서 응답을 반환하는 대신 예외로 요청을 중단하고 로그인 화면으로 이동한다.
    @app.exception_handler(WebAuthenticationRequired)
    async def authentication_required(request: Request, exc: WebAuthenticationRequired):
        # refresh 쿠키는 로그인 화면의 자동 복구 요청에서 검증한다.
        response = RedirectResponse("/login", status_code=303)
        response.headers["Cache-Control"] = "no-store"

        return response

# 인증 예외를 공통 오류 본문 형식과 Bearer 인증 응답으로 변환한다.
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from auth.domain.exceptions import AuthenticationError

logger = logging.getLogger(__name__)


def register_auth_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(
        request: Request, exc: AuthenticationError
    ) -> JSONResponse:
        # 로그인 ID, 입력 비밀번호, 토큰 원문은 기록하지 않는다.
        logger.warning(
            "authentication_error code=%s method=%s path=%s",
            exc.code, request.method, request.url.path,
        )
        return JSONResponse(
            status_code=401,
            content={"detail": {"code": exc.code, "message": exc.message}},
            headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
        )

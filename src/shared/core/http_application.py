"""기존 FastAPI 오류 응답까지 CORS와 HTTP 로깅으로 감싼다."""

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

from shared.core.http_middleware import RequestLoggingMiddleware


class HttpApplication(FastAPI):
    def __init__(self, *, cors_origins: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self.cors_origins = cors_origins

    def build_middleware_stack(self) -> ASGIApp:
        # add_middleware는 FastAPI의 최종 500 처리 안쪽에 등록된다.
        # 그 바깥을 감싸야 예상 밖 오류 응답에도 CORS/시간 헤더가 붙는다.
        # 기존 라우터, exception handler, dependency_overrides는 그대로 유지한다.
        stack = super().build_middleware_stack()
        stack = CORSMiddleware(
            stack,
            allow_origins=self.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
            expose_headers=["X-Process-Time"],
        )
        return RequestLoggingMiddleware(stack)

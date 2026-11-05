# 도메인 업무 오류와 예상 밖 서버 오류를 공통 HTTP 응답으로 변환한다.
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from shared.core.exceptions import (
    AppError,
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)

# 모듈 logger를 얻는다. 출력 형식과 대상은 shared.core.logging_config에서 설정한다.
logger = logging.getLogger(__name__)


def _unexpected_error_response(request: Request, exc: Exception) -> JSONResponse:
    # 예외 메시지와 입력 데이터 대신 종류, method와 path만 기록해 내부 정보를 보호한다.
    logger.error(
        "unexpected_error type=%s method=%s path=%s",
        type(exc).__name__,
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "서버 내부 오류가 발생했습니다.",
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    # 공통 부모에 등록하면 market 등 각 도메인의 자식 예외도 이 함수가 처리한다.
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        if isinstance(exc, BusinessRuleError):
            status_code = 400
        elif isinstance(exc, ForbiddenError):
            status_code = 403
        elif isinstance(exc, NotFoundError):
            status_code = 404
        elif isinstance(exc, ConflictError):
            status_code = 409
        else:
            # 분류되지 않은 업무 예외를 사용자 잘못으로 간주하지 않는다.
            return _unexpected_error_response(request, exc)

        # 응답의 code/message는 구체적인 도메인 예외의 값을 사용한다.
        logger.warning(
            "application_error code=%s method=%s path=%s",
            exc.code,
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=status_code,
            content={"detail": {"code": exc.code, "message": exc.message}},
        )

    # 별도의 업무 핸들러로 처리되지 않은 오류의 마지막 500 응답을 등록한다.
    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        # DB rollback은 기존 get_db가 담당한다. 이 함수는 기록과 응답 생성만 수행한다.
        return _unexpected_error_response(request, exc)


# 테스트 클라이언트에는 500 응답 전송 뒤 원래 예외가 다시 전달될 수 있다.
# 응답 전송 여부와 예외 전달 여부를 구분해서 검증한다.

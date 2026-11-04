"""예외를 JSON 응답으로 바꾸는 핸들러

- 도메인 예외(AppError와 자식)는 상태 코드와 {"detail": {...}} 본문으로 바꾼다
- 도메인 계층 예외(순수 파이썬의 ValueError 하위)는 대응표로 도메인 예외에 연결한다
  대응표 모양: {도메인 계층 예외: (도메인 예외 자식 클래스, "에러 코드")}
- common_item은 도메인을 import하지 않는다. 대응표는 각 도메인의 presentation이 적어서 등록한다
- 요청 값 검증 실패(422)는 우리가 정한 코드와 메시지만 준다
- 없는 경로(404), 허용되지 않은 메서드(405) 같은 HTTP 오류도 같은 형식으로 바꾼다
- 예상 못 한 오류(500)는 내부 내용을 숨기고 일반 문구만 보낸다
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from common_item.app_logging import get_logger

from common_item.exceptions import (
    AppError,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationFailedError,
)

_logger = get_logger('handlers')

# ===== 상태 코드표 =====

# [AppError] 도메인 상태 코드표 (exceptions.py에서 이미 만든 예외)
_STATUS_TO_ERROR = {
    401: UnauthorizedError,
    403: ForbiddenError,
    404: NotFoundError,
    422: ValidationFailedError,
    429: RateLimitedError,
    503: ServiceUnavailableError,
}

# [NoneAppError] 아래 명시한 오류 포함 위 표에 없는 모든 상태 코드
# 직접 던질 일이 생기면 그때 클래스로 올린다
# (참고) 여기 400은 방어용이고, exceptions.py의 400(팀 규칙 위반)과는 다르다
_STATUS_TO_CODE_MESSAGE = {
    400: ('BAD_REQUEST', '잘못된 요청입니다.'),
    405: ('METHOD_NOT_ALLOWED', '허용되지 않은 요청 방식입니다.'),
}


# ===== 도우미 함수 =====

# [AppError] 도메인 예외를 응답으로 바꾼다
def _to_response(error: AppError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content=error.to_body())


# [NoneAppError/AppError] 대응표 항목별로 핸들러를 만들어 돌려주는 팩토리 함수
# 순수 파이썬의 ValueError와 같이 메세지 글자뿐인 도메인 계층 예외를 도메인 예외로 번역한다
def _make_domain_handler(app_error_class: type[AppError], code: str):

    async def handler(request: Request, exc: Exception) -> JSONResponse:
        # 도메인 계층 예외에 메시지가 있으면 그걸 쓰고, 없으면 우리 예외의 기본 메시지를 쓴다
        return _to_response(app_error_class(str(exc) or None, code=code))

    return handler


# [NoneAppError] FastAPI HTTP 오류의 본문을 우리 형식으로 만든다
def _http_error_body(exc: StarletteHTTPException) -> dict:
    detail = exc.detail

    # 1. 이미 {'code', 'message'} 모양이면 그대로 쓴다 (직접 이 모양으로 던진 경우)
    if isinstance(detail, dict) and 'code' in detail and 'message' in detail:
        return {'detail': detail}

    # 2. [AppError] 표에 있는 상태 코드면 그 예외의 기본 본문을 쓴다
    error_class = _STATUS_TO_ERROR.get(exc.status_code)
    if error_class is not None:
        return error_class().to_body()

    # 3. 그 외는 [NoneAppError] 표에서 찾고, 거기도 없으면 HTTP_ERROR와 FastAPI가 준 글자를 쓴다
    code, message = _STATUS_TO_CODE_MESSAGE.get(exc.status_code, ('HTTP_ERROR', str(detail)))
    return AppError(message, code=code).to_body()


# ===== 핸들러 =====

# [AppError] 도메인 예외(AppError와 자식)를 받는다
# 이미 지정한 형식(상태 코드, code, message)이라 그대로 꺼내 쓴다
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _to_response(exc)


# [NoneAppError] FastAPI/Starlette의 HTTP 오류(없는 경로 404, 허용 안 된 메서드 405 등)를 받는다
# detail이 글자("Not Found")라 우리 형식으로 바꾸고, 인증 헤더 같은 exc.headers는 유지한다
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_http_error_body(exc),
        headers=exc.headers,
    )


# [NoneAppError] 요청 값 검증 실패(RequestValidationError)를 받는다
# 실패한 필드 목록(exc.errors())은 버리고 고정 본문(422)만 준다
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # 나중에 클라이언트가 실패한 필드를 화면에 표시하고 싶어 하면
    # exc.errors()의 loc에서 이름을 뽑아 params={'fields': [...]}로 추가한다
    return _to_response(ValidationFailedError())


# [NoneAppError] 위 어디에도 걸리지 않는 모든 Exception(코드 버그 등)을 받는다
# 내부 정보가 섞여 있을 수 있어서 내용은 숨기고 500 일반 문구만 준다
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # 오류 내용은 로그에만 남기고 응답에는 넣지 않는다
    _logger.error('처리되지 않은 오류: %s %s', request.method, request.url.path, exc_info=exc)
    return _to_response(AppError())


# ===== 등록 =====
# FastAPI는 터진 예외의 가장 가까운 부모 클래스로 등록된 핸들러를 고른다
# (NotFoundError -> AppError 핸들러, 없는 URL -> HTTP 핸들러, 그 외 -> Exception 핸들러)

def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)


# 도메인 계층 예외를 도메인 예외로 연결해서 등록한다 (대응표는 각 도메인의 presentation이 넘긴다)
# 새 도메인 계층 예외를 만들면 각 도메인의 presentation 대응표에도 한 줄 추가해야 한다
#   1. domain: class NotOwnerError(ValueError)
#   2. presentation: {NotOwnerError: (ForbiddenError, "NOT_OWNER")}
#   3. 앱 시작 때: register_domain_errors(app, 대응표)
# 대응표에 없으면 처리되지 않은 오류로 보고 500이 된다
def register_domain_errors(
    app: FastAPI, mapping: dict[type[Exception], tuple[type[AppError], str]]
) -> None:
    # 반복문의 마지막 값만 남지 않도록 팩토리 함수로 값을 고정해서 넘긴다
    for domain_error, (app_error_class, code) in mapping.items():
        app.add_exception_handler(domain_error, _make_domain_handler(app_error_class, code))
"""공통 예외
모든 도메인이 이 예외를 물려받아 자기 예외를 만든다.
- 부모 예외 하나 + 공통 자식(401·403·404·422·429·500·503)과 업무 규칙 위반(400)
- 본문 모양: {"detail": {"code", "message", "params"}} (params는 없으면 뺀다)
- 업무 규칙 위반은 400으로 통일한다(409 사용 안 함)
- 순수 파이썬만 쓴다. fastapi import 금지 (예외 -> HTTP 변환은 handlers.py가 한다)
"""

from typing import Any

# 형식이 맞지 않는 경우
# 자식이 동일한 JSON 응답이 되도록 부모 만들기 (기본값: 500)
# -> 자식이 새로 생겨도 핸들러 수정을 굳이 하지 않아도 된다
# -> 예외 코드를 정하지 않고 던지는 실수를 막기 위한 구조 
class AppError(Exception):

    # 안전한 기본값: 어떤 종류인지 모를 땐 사용자보다 일단 서버 탓하기 
    # 500 에러를 별도로 정의하지 않기 -> 일부러 서버 오류를 내는 이상한 형태 방지 
    status_code: int = 500
    code: str = 'INTERNAL_ERROR'
    message: str = '서버에서 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'

    def __init__(
            self,
            message: str|None=None,
            *,
            code: str|None=None,
            params: dict[str, Any]|None=None,
    ) -> None:

        if message is not None:
            self.message = message
        if code is not None:
            self.code = code
        self.params = params
        super().__init__(self.message)

    def to_body(self) -> dict[str, Any]:
        detail: dict[str, Any] = {'code': self.code, 'message':self.message}
        if self.params:
            detail['params'] = self.params
        return {'detail':detail}

# 부모에 기본값을 주지 않고 자식이 정하게 할 경우
# 부모를 그대로 던지면 오류 발생 
# class AppError(Exception):
#     status_code: int
#     code: str
#     message: str
# 자식이 code를 빼먹으면 오류 발생 
# class NotFoundError(AppError):
#     status_code = 404
#     code = 'NOT_FOUND'
#     message = '...'

# 형식은 맞지만 규약을 어긴 경우 / AppError를 상속받는다. (타입 생략)
class RuleError(AppError):
    status_code = 400
    code = 'RULE_VIOLATION'
    message = '요청을 처리할 수 없습니다.'

class UnauthorizedError(AppError):
    status_code = 401
    code = 'UNAUTHORIZED'
    message = '로그인이 필요하거나 토큰이 만료되었습니다.'

class ForbiddenError(AppError):
    status_code = 403
    code = 'FORBIDDEN'
    message = '이 기능을 사용할 권한이 없습니다.'

class NotFoundError(AppError):
    status_code = 404
    code = 'NOT_FOUND'
    message = '요청한 대상을 찾을 수 없습니다.'

class ValidationFailedError(AppError):
    status_code = 422
    code = 'VALIDATION_ERROR'
    message = '요청 값이 올바르지 않습니다.'

class RateLimitedError(AppError):
    status_code = 429
    code = 'RATE_LIMITED'
    message = '요청이 너무 많습니다. 잠시 후 다시 시도해주세요.'

class ServiceUnavailableError(AppError):
    status_code = 503
    code = 'SERVICE_UNAVAILABLE'
    message = '서버가 일시적으로 요청을 처리할 수 없습니다. 잠시 후 다시 시도해주세요.'
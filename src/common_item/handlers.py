"""예외를 JSON 응답으로 바꾸는 핸들러

- 우리 예외(AppError와 자식)는 상태 코드와 {"detail": {...}} 본문으로 바꾼다
- 도메인 예외(순수 파이썬의 ValueError 하위)는 대응표로 우리 예외에 연결한다
  대응표 모양: {도메인 예외: (우리 예외 자식 클래스, "에러 코드")}
- common_item은 도메인을 import하지 않는다. 대응표는 각 도메인의 presentation이 적어서 등록한다
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from common_item.exceptions import AppError

# 도우미 함수: 예외를 응답으로 바꾸기 
def _to_response(error: AppError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content=error.to_body())

async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _to_response(exc)

# 도우미 함수: 에러별 핸들러 생성하기 (함수를 만들어 돌려주는 팩토리 함수)
def _make_domain_handler(app_error_class: type[AppError], code: str):

    async def handler(request: Request, exc: Exception) -> JSONResponse:
        # 도메인 예외 메시지가 있으면 그걸 쓰고 없으면 내껄 쓴다
        return _to_response(app_error_class(str(exc) or None, code=code))
    return handler

# 이벤트 핸들러 등록
def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)

# 내 에러 대응은 presentation이 던지고 여기서 받을 예정
def register_domain_errors(
        app: FastAPI, mapping: dict[type[Exception], tuple[type[AppError], str]]
    ) -> None:
    # handler가 실행되는 그 시점에 반복문의 마지막 값만 남지 않도록 
    # 팩토리 함수를 불러서 값 고정
    for domain_error, (app_erorr_class, code) in mapping.items():
        app.add_exception_handler(domain_error, _make_domain_handler(app_erorr_class, code))
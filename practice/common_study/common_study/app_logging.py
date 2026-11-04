"""공통 로깅

- get_logger()
    - 각 파일이 기록을 남길 때마다 부르는 로거 → 여러 번 부르기 때문에 여러 번 기록될 수 있다
- setup_logging()
    - 역할: 로그가 어디에, 어떤 모양으로, 어느 수준부터 나올지 정하는 한 번의 설정
        - 별 다른 설정 없이 로그만 켜면 기록을 남기겠다고만 하지 화면이나 파일로 내보내지 않는다
        - 그래서 setup_logging() 같은 설정으로 기록을 내보내고 추적할 수 있도록 한다
        - 여기서 핸들러를 붙이면 get_logger()와 그 자식 로거는 핸들러를 굳이 붙이지 않아도 된다
    - 앱 시작 시점에 한 번 부르는 로거 → 한 번만 부르기 때문에 여러 번 기록되어선 안 된다
    - 여기서 세팅한 내용을 get_logger()(e.g. app.xxx)와 그 자식 로거가 따른다
    - 정하는 내용
        - 기록을 어디로 보낼지(handler)
            - 파이썬 표준 핸들러: StreamHandler, FileHandler, NullHandler, ...
        - 기록을 어떤 형태로 남길지(formatter)
        - 기록을 어디서부터 어디까지 할지(기본: INFO)
    - 중복 방지 옵션
        - 여러 번 불러도 핸들러가 쌓이지 않아야 하고 같은 기록이 부모(root)에 쌓여선 안된다
        - _MARK 꼬리표 + propagate = false 설정
- register_request_logging(app)은 요청마다 "메서드 경로 상태 소요시간" 한 줄을 남긴다
    - 쿼리 문자열은 민감할 수 있어 남기지 않는다
- 처리하지 못한 오류의 로그는 handlers.py의 unhandled_error_handler가 남긴다
"""

import logging
import time
from fastapi import FastAPI, Request


LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s %(filename)s:%(lineno)d %(message)s'

# 도메인 로거 전체의 부모 이름
# 한 번만 적어 두고 f-string으로 가져다 쓴다 (로거 이름을 바꾸고 싶으면 여기만 고치면 됨)
_ROOT_NAME = 'app'

# 도메인 핸들러에 달아 두는 꼬리표
# setup_logging()을 여러 번 불러도 핸들러가 쌓여 같은 기록이 두 줄 찍히지 않게 한다
_MARK = '_app_logging_handler'


def get_logger(name: str) -> logging.Logger:
    # 같은 이름으로 부르면 항상 같은 로거가 돌아온다 (logging이 이름별로 하나씩 기억한다)
    # 이름을 "app.이름"으로 만들면 "app" 로거가 부모가 되어, 부모에 설정을 자식이 따른다
    return logging.getLogger(f'{_ROOT_NAME}.{name}')



def setup_logging(level: int = logging.INFO, handler: logging.Handler|None=None) -> None:
    # 앱을 시작할 때 한 번 부른다. 부모 로거에 보낼 곳, 모양, 레벨을 정한다
    logger = logging.getLogger(_ROOT_NAME)

    # 1단계: 이전에 붙인 핸들러가 있으면 뗀다 (꼬리표가 있는 것만)
    #   logger.handlers는 지금 붙어 있는 핸들러 목록이고, getattr(h, _MARK, False)는
    #   "꼬리표 속성이 있으면 그 값(True), 없으면 False"라는 뜻이다
    #   목록을 도는 중에 목록을 고치면 꼬이니까 [ ]로 복사본을 먼저 만들어 그것을 돈다
    for old in [h for h in logger.handlers if getattr(h, _MARK, False)]:
        logger.removeHandler(old)

    # 2단계: 쓸 핸들러를 정한다. handler가 None이면 or 뒤의 화면 출력용 핸들러를 쓴다
    #   그리고 기록의 모양(LOG_FORMAT)을 붙이고, "우리가 붙였다"는 꼬리표를 단다
    handler = handler or logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    setattr(handler, _MARK, True)

    # 3단계: 로거에 핸들러와 레벨을 붙인다
    logger.addHandler(handler)
    logger.setLevel(level)
    # 기록이 부모(root 로거)로도 올라가서 같은 줄이 한 번 더 찍히는 것을 막는다
    logger.propagate = False


def register_request_logging(app: FastAPI) -> None:
    # 요청이 올 때마다 한 줄을 남기는 미들웨어를 앱에 등록한다 (앱 시작 때 한 번 부른다)
    # 미들웨어: 모든 요청이 라우터에 닿기 전과 응답이 나간 뒤에 거치는 공통 통로
    logger = get_logger('request')

    @app.middleware('http')
    async def log_request(request: Request, call_next):
        # 요청이 들어왔을 때 시계를 켠다
        start = time.perf_counter()
        # call_next(request): 이 요청을 다음 단계(라우터 등)로 넘겨 처리하게 하고 응답을 받는다
        response = await call_next(request)
        # 처리가 끝난 뒤 걸린 시간을 ms(밀리초)로 바꾼다 (초 x 1000)
        ms = (time.perf_counter()-start)*1000
        # 경로는 request.url.path만 쓴다. 
        # 쿼리 문자열(?token=...)에 토큰이 있을 수 있어서 남기지 않는다
        # 결과 예: GET /v1/inventory 200 3.1ms
        logger.info('%s %s %s %.1fms', request.method, request.url.path, response.status_code, ms)
        return response

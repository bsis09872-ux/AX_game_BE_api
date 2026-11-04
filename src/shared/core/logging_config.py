# 앱 전체의 로그 형식과 콘솔 출력을 설정한다.
from logging.config import dictConfig


def setup_logging() -> None:
    # import만으로 실행되지 않으며 앱 시작 준비에서 호출한다.
    dictConfig(
        {
            # 설정 딕셔너리의 스키마 버전. dictConfig가 요구하는 값은 1이다.
            "version": 1,
            # Uvicorn 등 이미 존재하는 logger를 비활성화하지 않는다.
            "disable_existing_loggers": False,
            # formatter는 출력 모양이다. 시간, 레벨, 모듈 이름과 메시지를 채운다.
            "formatters": {
                "standard": {
                    "format": (
                        "%(asctime)s | %(levelname)-7s | "
                        "%(name)s (%(filename)s:%(lineno)d) | %(message)s"
                    ),
                    "datefmt": "%H:%M:%S",
                }
            },
            # handler는 출력 대상이다. standard 형식으로 표준 오류 스트림(콘솔)에 기록한다.
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "stream": "ext://sys.stderr",
                }
            },
            # 기본 상위 logger가 INFO 이상을 콘솔에 출력한다. DEBUG는 생략된다.
            "root": {"level": "INFO", "handlers": ["console"]},
        }
    )


# 각 모듈에서는 logging.getLogger(__name__)으로 얻고 별도 handler는 붙이지 않는다.
# 비밀번호, 비밀번호 해시, JWT, DATABASE_URL과 요청 본문 전체는 기록하지 않는다. (보안 유지)

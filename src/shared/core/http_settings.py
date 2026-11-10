"""CORS에서 허용할 브라우저 Origin을 환경변수로 읽는다."""

import os
from urllib.parse import urlsplit


def read_cors_origins() -> list[str]:
    # 별도 설정이 없으면 기존 웹 화면 주소만 허용한다.
    # 명시적으로 빈 문자열을 설정하면 교차 Origin 허용 목록을 비운다.
    value = os.environ.get("CORS_ALLOWED_ORIGINS")
    if value is None:
        value = os.environ.get("WEB_ORIGIN", "http://127.0.0.1:8000")

    origins = []
    for entry in value.split(","):
        origin = entry.strip().rstrip("/")
        if not origin:
            continue

        try:
            parsed = urlsplit(origin)
            valid = (
                parsed.scheme in {"http", "https"}
                and parsed.hostname
                and not parsed.path
                and not parsed.query
                and not parsed.fragment
                and not parsed.username
                and not parsed.password
                and "*" not in origin
                and not any(character.isspace() or ord(character) < 32 for character in origin)
            )
            # 잘못된 포트 번호도 앱을 시작하기 전에 거절한다.
            parsed.port
        except ValueError:
            valid = False

        if not valid:
            raise ValueError("CORS_ALLOWED_ORIGINS에는 http/https Origin만 쉼표로 구분해 지정하세요.")

        if origin not in origins:
            origins.append(origin)

    return origins

# 공통 모듈 안내

[프로젝트 구조 안내](../../../docs/project-structure.md) · [앱 진입점](../../main.py)

여러 도메인이 함께 사용하는 로깅 설정과 예외 처리 모듈입니다. 구체적인 업무 규칙과 오류는 각 도메인에서 정의합니다.

## 현재 구성

| 파일 | 역할 |
| --- | --- |
| [logging_config.py](logging_config.py) | 로그 형식·레벨·출력 대상 설정. 현재 INFO 이상을 콘솔에 출력 |
| [exceptions.py](exceptions.py) | 공통 예외 기반 AppError와 업무 규칙·미존재·충돌 분류 |
| [exception_handlers.py](exception_handlers.py) | 예외를 HTTP 오류 응답으로 변환하고 로그 기록 |
| [http_settings.py](http_settings.py) | CORS 허용 Origin 환경변수 검증 |
| [http_middleware.py](http_middleware.py) | HTTP 요청 결과 로그와 처리 시간 헤더 |
| [http_application.py](http_application.py) | FastAPI의 최종 오류 응답까지 CORS와 요청 로그 적용 |

DB 엔진·세션·Base는 [src/database.py](../../database.py)에서 관리합니다. 이 폴더에는 별도 database.py, models.py, schemas.py가 없습니다.

## 앱 연결과 사용

- [main.py](../../main.py)의 lifespan에서 `setup_logging()`을 호출하고, 앱 생성 후 `register_exception_handlers(app)`를 등록합니다. 현재 적용되어 있습니다.
- 각 모듈은 `logging.getLogger(__name__)`으로 로거를 얻습니다. 저장 성공 로그는 commit 성공 후 남깁니다.
- 각 도메인의 `domain/exceptions.py`에서 공통 예외를 상속하고, 상황에 맞는 `code`와 `message`를 정의해 발생시킵니다.

## 현재 오류 처리

| 예외 분류 | HTTP 상태 | 로그 |
| --- | --- | --- |
| BusinessRuleError | 400 | WARNING |
| NotFoundError | 404 | WARNING |
| ConflictError | 409 | WARNING |
| 분류되지 않은 AppError·예상 밖 오류 | 500 | ERROR |

오류 응답은 `detail` 안에 `code`와 `message`를 담습니다. HTTP 상태는 핸들러가 예외 타입에 따라 결정하며, 500 응답은 내부 원인을 노출하지 않습니다. 이 변환은 HTTP 요청 처리에 적용되며 도메인 직접 호출은 Python 예외를 발생시킵니다.

## 변경할 때

- 로그 형식·레벨·출력 대상은 logging_config.py에서 변경합니다.
- 기존 오류 분류의 자식 예외는 도메인에 추가합니다. 새로운 HTTP 상태를 지원하려면 공통 분류와 핸들러 매핑을 함께 추가합니다.
- 입력 검증 오류(422)는 입력 원문을 제외합니다. HTTPException 응답 형태는 기존 FastAPI 규격을 유지합니다.
- 전역 핸들러가 기록하는 예외를 발생 지점에서 중복 기록하지 않습니다. 비밀번호·해시·JWT·DB 접속 정보·요청 본문 전체는 로그에 남기지 않습니다.

## HTTP 미들웨어 설정과 검증

`main.py`는 FastAPI를 상속한 `HttpApplication`을 사용합니다. 기본 오류 처리의 바깥에 CORS와 로깅을 배치하므로 예상 밖 500 응답에도 허용 Origin과 처리 시간 헤더가 붙습니다. 기존 라우터와 인증 의존성은 유지합니다.

- `CORS_ALLOWED_ORIGINS`: 쉼표로 구분한 http/https Origin 목록. 미설정이면 `WEB_ORIGIN`을 사용하고, 둘 다 없으면 `http://127.0.0.1:8000`을 사용합니다. 명시적인 빈 문자열은 교차 Origin 허용 목록을 비웁니다.
- 쿠키 인증을 위해 credentials를 허용하며, Origin의 `*`는 거절합니다. 허용 메서드는 GET/HEAD/POST/PUT/PATCH/DELETE/OPTIONS이고 요청 헤더는 Authorization/Content-Type입니다.
- CORS 목록에 추가해도 기존 쿠키 쓰기 요청의 `WEB_ORIGIN` 검사는 완화되지 않습니다. 웹 화면을 다른 Origin으로 분리하는 것은 별도 인증 설계가 필요합니다.
- HTTP 요청마다 method/path/status/duration_ms/failed를 한 번 기록합니다. 오류 상세 로그와 요청 결과 로그는 역할이 다릅니다. query string, 요청/응답 본문, 인증 헤더, 쿠키는 기록하지 않습니다.
- `duration_ms`와 `X-Process-Time`은 요청 시작부터 응답 헤더 생성까지의 시간입니다. 헤더 단위는 초입니다. 스트리밍 본문 전송 및 background task 완료 시간은 포함하지 않습니다. 브라우저에 헤더를 노출하도록 CORS expose_headers에 등록합니다.
- 헤더 전송 이후 스트림이 실패하면 이미 전송한 상태 코드와 failed=true를 기록하고 원래 예외를 전달합니다. WebSocket과 lifespan 메시지는 그대로 통과시킵니다.

검증 명령:

```bash
uv run --frozen --with httpx python scripts/verify-http-middleware.py
```

12개 테스트로 CORS preflight/거절, 쿠키 Origin 검사, 200/401/403/404/422/500, 민감정보 비기록, 시간 단위, 동시 요청, 스트리밍, WebSocket, 실제 main 연결을 검증합니다. 테스트는 lifespan을 실행하지 않고 실제 앱의 DB 연결을 차단하므로 기존 DB나 경매 스케줄러를 실행하지 않습니다.

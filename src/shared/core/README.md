# 공통 모듈 안내

[프로젝트 구조 안내](../../../docs/project-structure.md) · [앱 진입점](../../main.py)

여러 도메인이 함께 사용하는 로깅 설정과 예외 처리 모듈입니다. 구체적인 업무 규칙과 오류는 각 도메인에서 정의합니다.

## 현재 구성

| 파일 | 역할 |
| --- | --- |
| [logging_config.py](logging_config.py) | 로그 형식·레벨·출력 대상 설정. 현재 INFO 이상을 콘솔에 출력 |
| [exceptions.py](exceptions.py) | 공통 예외 기반 AppError와 업무 규칙·미존재·충돌 분류 |
| [exception_handlers.py](exception_handlers.py) | 예외를 HTTP 오류 응답으로 변환하고 로그 기록 |

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
- 입력 검증 오류(422)·HTTPException의 응답 통일과 전체 요청/응답 로깅은 추가 구현이 필요합니다.
- 전역 핸들러가 기록하는 예외를 발생 지점에서 중복 기록하지 않습니다. 비밀번호·해시·JWT·DB 접속 정보·요청 본문 전체는 로그에 남기지 않습니다.

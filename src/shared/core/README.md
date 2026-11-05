 # 공통 (모든 도메인이 사용)
 ##### 작성 순서 : logger → exceptions → schemas → exception_handlers → database → models

 ## logger.py
   - 환경 변수로 레벨 결정 (debug / info)
   - 형식: 시간, 레벨, 로거 이름, 메시지
   - get_logger(이름) 함수 하나만 외부에 공개

## exceptions.py
   - 공통 부모 예외 1개: message, status_code, error_code, errors를 가짐
   - 자식들: 400 / 401 / 403 / 404 / 409 / 422
   - 자식은 상태 코드만 고정하고, 기본 메시지만 다르게

## schemas.py
   - 공통 응답 모델: success, code, message, errors, data, (응답 시각)
   - data 타입을 바꿔 끼울 수 있게 Generic으로
   - 성공용 / 실패용 생성 함수 2개 (클래스 메서드)

## exception_handlers.py
   - 등록 함수 하나 안에 핸들러 3개
##### ① 공통 부모 예외 → 해당 상태 코드 + 실패 응답, warning 로그
##### ② 요청 검증 실패 → 422, 에러를 "필드명: [메시지들]" 형태로 정리
##### ③ 그 외 모든 예외 → 500, 내부 내용은 로그에만 남기고 응답에선 숨김

## database.py
   - 비동기 엔진 (커넥션 풀 옵션)
   - 세션 팩토리: autoflush 끔, expire_on_commit 끔
   - get_db: 세션 열기 → yield → 예외 시 rollback
   - close_db: 엔진 dispose

## models.py
   - Base (DeclarativeBase 상속, 내용 없음)
   - 시간 Mixin: created_at / modified_at / deleted_at
       ##### → 기본값은 "함수 자체"를 넘길 것 (호출 결과 X)
   - init_models: 도메인 ORM 모델 파일들을 함수 안에서 import
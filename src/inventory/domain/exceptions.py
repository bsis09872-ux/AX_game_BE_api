"""도메인 계층 예외

- 업무 규칙을 어기면 도메인이 스스로 던지는 예외들이다 (모두 ValueError 하위)
- HTTP 상태 코드와 에러 코드를 모른다. HTTP 오류로 바꾸는 일은 presentation이 맡는다
- 이름은 "의미 + Error" 형식이다 (예: NotOwnerError)
- 예외의 글자(메시지)로 분기하지 않고 예외 클래스로 구분한다
- 새 예외를 만들면 presentation의 오류 변환 표에도 한 줄을 추가한다
- 순수 파이썬만 쓴다 (FastAPI, Pydantic, SQLAlchemy, logging을 import하지 않는다)
"""

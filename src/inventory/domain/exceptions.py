"""도메인 계층 예외

- 업무 규칙을 어기면 도메인이 스스로 던지는 예외들이다
- 팀 공통 shared.core.exceptions의 분류를 상속한다: BusinessRuleError(400), NotFoundError(404), ConflictError(409)
- 각 예외는 code와 message를 클래스에 적는다. 상태 코드는 팀 공통 핸들러가 부모 분류로 정한다
- 이 도메인에서만 필요한 상태 코드(403, 429, 503)는 presentation의 이 도메인 전용 핸들러가 정한다
- 이름은 "의미 + Error" 형식이다 (예: NotOwnerError)
- 예외의 글자(메시지)로 분기하지 않고 예외 클래스로 구분한다
- FastAPI, Pydantic, SQLAlchemy, logging을 import하지 않는다 (shared.core.exceptions는 순수 파이썬이라 import해도 된다)
"""

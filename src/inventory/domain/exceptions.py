"""도메인 계층 예외

- 업무 규칙을 어기면 도메인이 스스로 던지는 예외들이다
- 팀 공통 shared.core.exceptions의 분류를 상속한다: BusinessRuleError(400), NotFoundError(404), ConflictError(409)
- 각 예외는 code와 message를 클래스에 적는다. 상태 코드는 팀 공통 핸들러가 부모 분류로 정한다
- 팀 공통에 없는 상태 코드는 팀 공통 파일(shared.core)에 분류를 추가해서 쓴다
- 이름은 "의미 + Error" 형식이다 (예: NotOwnerError)
- 예외의 글자(메시지)로 분기하지 않고 예외 클래스로 구분한다
- FastAPI, Pydantic, SQLAlchemy, logging을 import하지 않는다 (shared.core.exceptions는 순수 파이썬이라 import해도 된다)
"""

from shared.core.exceptions import AppError, BusinessRuleError, ConflictError, NotFoundError, ForbiddenError

# 400: 카탈로그를 만들거나 고칠 때 규칙을 어긴 경우
class ItemRuleViolationError(BusinessRuleError):
    code: str = 'ITEM_RULE_VIOLATION'
    message: str = '아이템 카탈로그의 값이 규칙과 맞지 않습니다.'

# 400: 변경 불가능한 속성을 수정하려고 하는 경우
class DefinitionImmutableFieldError(BusinessRuleError):
    code: str = 'DEFINITION_IMMUTABLE'
    message: str = '이름과 카테고리는 값을 변경할 수 없습니다.'

# 400: 경매로 얻은 아이템을 재판매 대기 시간 내 판매하려는 경우
class ResaleNotAvailableError(BusinessRuleError):
    code: str = 'RESALE_NOT_AVAILABLE'
    message: str = '경매로 얻은 아이템의 즉시 재판매는 불가합니다.'

# 409: 아이템 상태가 요청과 맞지 않는 경우 (잠금 상태인데 등록됐다거나 보관 중인데 낙찰 등)
class InvalidStateError(ConflictError):
    code: str = 'ITEM_STATE_CONFLICT'
    message: str = '아이템 상태가 요청과 맞지 않습니다.'

# 404: 없는 아이템이거나 다른 소유자의 아이템을 조회한 경우 
class ItemNotFoundError(NotFoundError):
    code: str = 'ITEM_NOT_FOUND'
    message: str = '아이템을 찾을 수 없습니다.'

# 404: 없는 아이템 카탈로그를 조회한 경우
class DefinitionNotFoundError(NotFoundError):
    code: str = 'DEFINITION_NOT_FOUND'
    message: str = '아이템 카탈로그를 찾을 수 없습니다.'

# 404: 아이템을 받을 사용자가 없거나 탈퇴한 경우
class OwnerNotFoundError(NotFoundError):
    code: str = 'OWNER_NOT_FOUND'
    message: str = '아이템을 받을 사용자를 찾을 수 없습니다.'

# 403: 소유자가 아닌 사람이 아이템 상태 변경을 시도하는 경우
class NotOwnerError(ForbiddenError):
    code: str = 'NOT_OWNER'
    message: str = '해당 아이템 소유자가 아닙니다.'

# 400: 관리자가 이미 있는 code로 카탈로그를 생성하려는 경우
class DefinitionCodeDuplicateError(BusinessRuleError):
    code: str = 'DEFINITION_CODE_DUPLICATE'
    message: str = '이미 있는 아이템 카탈로그 입니다.'

# 400: 관리자가 유저가 보유 중인 아이템 카탈로그를 삭제하려는 경우
class DefinitionInUseError(BusinessRuleError):
    code: str = 'DEFINITION_IN_USE'
    message: str = '이 카탈로그의 아이템을 유저가 보유하고 있어 삭제할 수 없습니다. 추가 지급을 막으려면 fishable을 false로 바꾸세요.'

# 503: 낚시로 나올 수 있는 카탈로그가 하나도 없는 경우
class NoFishableDefinitionError(AppError):
    code: str = 'FISHING_NO_REWARD'
    message: str = '지금은 낚을 수 있는 아이템이 없습니다.'
# 회원 정보 검증, 회원 조회, 로그인 ID 중복에 대한 도메인 예외를 정의한다.

from shared.core.exceptions import BusinessRuleError, ConflictError, NotFoundError

# 회원 정보의 규칙 위반을 나타내며, 전역 처리기가 400 응답과 WARNING 로그를 담당한다.
class InvalidUserError(BusinessRuleError):
    code: str = "INVALID_USER"
    message: str = "회원 정보가 유효하지 않습니다."

# 회원 조회 실패를 나타내며, 전역 처리기가 404 응답과 WARNING 로그를 담당한다.
class UserNotFoundError(NotFoundError):
    code: str = "USER_NOT_FOUND"
    message: str = "회원을 찾을 수 없습니다."

# 가입하려는 로그인 ID가 이미 사용 중일 때 전역 핸들러가 409로 응답한다.
class LoginIdAlreadyExistsError(ConflictError):
    code: str = "LOGIN_ID_ALREADY_EXISTS"
    message: str = "이미 사용 중인 로그인 ID입니다."


class AdminAccountProtectionError(ConflictError):
    code = 'ADMIN_ACCOUNT_PROTECTED'
    message = '관리 가능한 관리자 계정을 유지해야 합니다.'

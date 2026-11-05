# 회원 정보 검증 실패와 회원 조회 실패를 구분하는 도메인 예외를 정의한다.

from shared.core.exceptions import BusinessRuleError, ConflictError, NotFoundError

# 회원 정보의 규칙 위반을 나타내며, 전역 처리기가 400 응답과 WARNING 로그를 담당한다.
class InvalidUserError(BusinessRuleError):
    code: str = "INVALID_USER"
    message: str = "회원 정보가 유효하지 않습니다."

# 회원 조회 실패를 나타내며, 전역 처리기가 404 응답과 WARNING 로그를 담당한다.
class UserNotFoundError(NotFoundError):
    code: str = "USER_NOT_FOUND"
    message: str = "회원을 찾을 수 없습니다."
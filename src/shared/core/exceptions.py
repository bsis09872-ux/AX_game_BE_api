# 여러 도메인이 공유하는 오류의 큰 분류. 특정 판매글이나 회원의 규칙은 넣지 않는다.
# HTTP 상태 코드 결정은 presentation의 데코레이터/핸들러가 맡는다.
class AppError(Exception):
    code: str = "APPLICATION_ERROR"
    message: str = "오류가 발생했습니다."

    def __init__(self, message: str | None = None):
        self.message = self.message if message is None else message
        # 선택한 메시지를 부모에도 전달해 message와 str(exc)의 설명을 일치시킨다.
        super().__init__(self.message)


class BusinessRuleError(AppError):
    # 입력이 업무 규칙을 만족하지 못한 경우. 구체적인 이유는 각 도메인의 자식 예외가 표현한다.
    code: str = "BUSINESS_RULE_VIOLATION"
    message: str = "업무 규칙을 만족하지 못했습니다."


class NotFoundError(AppError):
    # 조회 대상이 없음. 판매글/회원 등 어떤 대상인지는 자식 예외의 code로 구분한다.
    code: str = "RESOURCE_NOT_FOUND"
    message: str = "요청한 대상을 찾을 수 없습니다."

class ConflictError(AppError):
    # 요청이 현재 상태와 충돌함. 이미 판매 완료된 글 같은 구체적인 상황은 도메인에서 정의한다.
    code: str = "RESOURCE_CONFLICT"
    message: str = "요청이 현재 상태와 충돌합니다."

class ForbiddenError(AppError):
    # 로그인을 했어도 권한이 없는 경우. 남의 자원을 바꾸는 등의 구체적인 상황은 도메인에서 정의한다.
    code: str = "FORBIDDEN"
    message: str = "요청을 수행할 권한이 없습니다."
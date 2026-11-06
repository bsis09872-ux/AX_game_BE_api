# 인증 실패를 HTTP와 분리해 표현한다. 구체적인 계정 상태는 외부에 공개하지 않는다.
from shared.core.exceptions import AppError


class AuthenticationError(AppError):
    code = "AUTHENTICATION_REQUIRED"
    message = "인증이 필요합니다."


class InvalidCredentialsError(AuthenticationError):
    code = "INVALID_CREDENTIALS"
    message = "로그인 ID 또는 비밀번호를 확인해 주세요."


class InvalidTokenError(AuthenticationError):
    code = "INVALID_TOKEN"
    message = "유효하지 않거나 만료된 인증 정보입니다."

from pydantic import BaseModel, Field


# [AUTH-01] 가입자가 입력하는 값만 받는다. 역할 지정과 비밀번호 해싱은 서버에서 처리한다.
class RegisterUserRequest(BaseModel):
    # 로그인 ID 제약은 User 도메인의 생성 규칙과 일치시킨다.
    login_id: str = Field(min_length=4, max_length=50, pattern="^[a-z0-9_]+$")
    display_name: str = Field(description="게임에 표시할 이름")
    password: str = Field(min_length=1)

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Literal

# [AUTH-01] 가입자가 입력하는 값만 받는다. 역할 지정과 비밀번호 해싱은 서버에서 처리한다.
class RegisterUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # 로그인 ID 제약은 User 도메인의 생성 규칙과 일치시킨다.
    login_id: str = Field(min_length=4, max_length=50, pattern="^[a-z0-9_]+$")
    display_name: str = Field(min_length=2, max_length=50, pattern=r"\S", description="게임에 표시할 이름")
    password: str = Field(min_length=1, max_length=1024, repr=False)


# 가입 완료 응답에 회원 ID, 로그인 ID와 가입 시각만 공개한다.
class RegisterUserResponse(BaseModel):
    # 라우터에서 정수 ID를 문자열로 변환하고 가입 시각은 UTC로 전달한다.
    id: str
    login_id: str
    created_at: datetime


# 클라이언트는 access_token을 Authorization: Bearer 헤더로 전달한다.
class TokenResponse(BaseModel):
    access_token: str = Field(repr=False)
    refresh_token: str = Field(repr=False)
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    refresh_expires_in: int


class RefreshTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(min_length=64, max_length=64, repr=False)

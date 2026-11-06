from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

from users.domain.user import User

# [AUTH-03] 본인 계정에서 클라이언트에 공개할 필드만 반환한다.
class UserMeResponse(BaseModel):
    id: str
    login_id: str
    created_at: datetime
    display_name: str
    # 화면은 이 값으로 운영자 메뉴를 표시하고, API 접근 권한은 서버에서 검사한다.
    role: Literal["USER", "ADMIN"]

    # 저장된 회원의 공개 필드를 응답 형식으로 변환한다.
    @classmethod
    def from_user(cls, user: User) -> "UserMeResponse":
        # 저장 결과의 필수 값과 시간대가 누락되면 내부 데이터 오류로 처리한다.
        if user.id is None or user.created_at is None:
            raise ValueError("회원 ID 또는 가입 시각이 없습니다.")

        if user.created_at.utcoffset() is None:
            raise ValueError("가입 시각에 시간대 정보가 없습니다.")

        return cls(
            id=str(user.id),
            login_id=user.login_id,
            created_at=user.created_at.astimezone(timezone.utc),
            display_name=user.display_name,
            role=user.role,
        )

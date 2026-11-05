from datetime import datetime
from typing import Literal

from pydantic import BaseModel


# [AUTH-03] 본인 계정에서 클라이언트에 공개할 필드만 반환한다.
class UserMeResponse(BaseModel):
    id: str
    login_id: str
    created_at: datetime
    display_name: str
    # 화면은 이 값으로 운영자 메뉴를 표시하고, API 접근 권한은 서버에서 검사한다.
    role: Literal["USER", "ADMIN"]

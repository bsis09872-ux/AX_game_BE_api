"""도메인 공통 응답·요청 스키마

- IdStr: 내부에서는 int, JSON 응답으로 나갈 때만 문자열로 직렬화되는 ID 타입
- PageParams / PageResponse: 목록 조회 공통 페이지네이션
"""
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, Field, PlainSerializer

# DB·도메인에서는 int로 다루고, 응답 JSON에서는 "123" 같은 문자열로 내보낸다.
# (JS Number는 2^53 이상의 정수를 정확히 표현하지 못하기 때문)
IdStr = Annotated[int, PlainSerializer(lambda v: str(v), return_type=str, when_used="json")]

T = TypeVar("T")


class PageParams(BaseModel):
    """쿼리 파라미터 ?page=1&size=20 (라우터에서 Depends()로 받는다)"""
    page: int = Field(1, ge=1, description="페이지 번호 (1부터 시작)")
    size: int = Field(20, ge=1, le=50, description="페이지당 개수 (최대 50)")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class PageResponse(BaseModel, Generic[T]):
    """목록 응답 공통 형태"""
    items: list[T]
    page: int
    size: int
    total: int

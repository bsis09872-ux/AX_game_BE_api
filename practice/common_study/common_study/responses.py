"""응답 모델

- 목록 응답: {"items", "page", "size", "total"}
- ID는 JSON에서 10진 문자열로 내보낸다. 값이 없으면 JSON null. DB·도메인은 int 그대로
- 금액·개수는 숫자 그대로 둔다
- 목록 쿼리(page, size)는 범위를 벗어나면 422
"""

from typing import Annotated, Generic, TypeVar
from fastapi import Query
from pydantic import BaseModel, PlainSerializer

# JSON으로 나갈 때만 문자열로 변환 (돌아가는 동안에는 원래 타입(int) 유지)
# Pydantic 제공 기능성 시리얼라이저 PlainSerializer 활용 커스텀 출력 변환
# 출력 변환 이유: 팀 규약에 근거함 (ID의 DB 타입은 유지하고 JSON에서 문자열로 변환)
# -> 파이썬이 돌아갈 때는 숫자 그대로가 빠르고 문자열 변환은 API 경계에서 한다. 
IdStr = Annotated[int, PlainSerializer(lambda v: str(v), return_type=str, when_used='json')]
T = TypeVar('T')

class PageResponse(BaseModel, Generic[T]):
    items: list[T]
    page: int
    size: int
    total: int

class PageParams:

    def __init__(
            self,
            page: int = Query(1, ge=1, description='페이지 번호, 1부터'),
            size: int = Query(20, ge=1, le=100, description='페이지 크기, 1~100'),
    ) -> None:
        self.page = page
        self.size = size

    # 목록 API마다 계산식을 쓰지 않도록 묶음 ('파라미터.offset' 형태로 쓰면 됨)
    @property
    def offset(self) -> int:
        return (self.page-1)*self.size
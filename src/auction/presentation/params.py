# HTTP 입력값의 공통 범위를 정의한다. (auth 관리자 라우터와 같은 기준)
# 범위를 넘는 값이 DB까지 가면 bigint 변환 오류로 500이 나므로, 입력 단계에서 422로 거절한다.
# 업무 규칙(시작가·최고가 비교 등)은 여기서 검사하지 않는다.

from typing import Annotated

from fastapi import Path, Query

# DB 컬럼 상한: ID·금액은 bigint, 페이지 번호는 int 범위까지 허용한다.
BIGINT_MAX = 9223372036854775807
INT_MAX = 2147483647

# 경로의 매물 ID: /listings/{listing_id}
ListingIdPath = Annotated[int, Path(ge=1, le=BIGINT_MAX)]

# 선택 조회 조건의 ID: ?listing_id=, ?buyer_id= 등. 없으면 None.
OptionalIdQuery = Annotated[int | None, Query(ge=1, le=BIGINT_MAX)]

# 페이지 번호: ?page=. 기본값은 사용하는 쪽에서 1로 지정한다.
PageQuery = Annotated[int, Query(ge=1, le=INT_MAX)]

# auction / presentation

HTTP 요청을 검증하고 application 결과를 응답으로 변환한다. 마감 스케줄러도 이 계층에 둔다.

## 파일 역할

| 파일 | 역할 |
|---|---|
| `listings/router.py` | `/v1/listings`: 목록·상세·등록·입찰·판매자 취소, 관리자 조회·강제 취소 (Bearer 인증) |
| `listings/admin_web_router.py` | `/admin/listings/{id}/cancel`: 관리자 웹 강제 취소 (HttpOnly 쿠키 인증) |
| `listings/schemas.py` | 매물 요청·응답 스키마 |
| `trades/router.py`·`trades/schemas.py` | `/v1/trades`: 내 낙찰·판매 내역, 입찰 제한 상태, 관리자 거래 조회 |
| `admin_router.py`·`admin_queries.py` | `/admin/auctions`·`/admin/auction-trades`: 관리자 화면(HTML) |
| `params.py` | 입력 범위 공통 타입 (ID·금액은 bigint, page는 int 범위) |
| `dependencies.py` | 서비스·인증 사용자 의존성 자리 표시자. wiring이 실제 구현으로 바꾼다 |
| `scheduler.py` | 5초마다 마감 정산을 실행하는 백그라운드 작업. main lifespan이 시작·종료한다 |

## 규칙

- 사용자 ID는 인증 의존성으로만 받는다. 본문의 사용자 ID를 신뢰하지 않는다.
- 웹 화면(JS)은 HttpOnly 쿠키의 토큰을 읽을 수 없으므로, 쿠키 인증 경로를 따로 둔다. 인증 의존성은 main.py가 넘겨 준다.
- 범위를 넘는 입력은 `params.py`로 422 처리한다. DB까지 보내지 않는다.
- 시각은 UTC ISO 8601로 반환한다. KST 표시는 화면이 담당한다.
- 입찰 제한 중에도 조회는 허용한다. 업무 예외는 전역 핸들러가 응답으로 바꾼다.
- SQL·정산·낙찰 제한 계산은 이 계층에 구현하지 않는다.
- [TO DO] 팀 공통 목록 응답 형식(size·total 포함 여부)을 확정한다. (진행 전)

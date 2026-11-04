"""인벤토리·카탈로그 조회 API 라우터 (/v1)

- GET /v1/inventory, GET /v1/inventory/{item_id}: 내 인벤토리 목록과 상세
- GET /v1/item-definitions, GET /v1/item-definitions/{definition_id}: 아이템 종류 목록과 상세
- 라우터는 입력 검증, 서비스 호출, 응답 변환만 한다 (업무 판정, DB 갱신, commit을 하지 않는다)
- 소유자 ID는 요청 값이 아니라 검증된 인증 정보에서 얻는다
- 도메인 계층 예외를 HTTP 오류로 바꾸는 표는 이 계층에서 적는다 (변환 방식은 팀 공통 방식을 따른다)
"""

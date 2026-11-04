"""인벤토리·카탈로그 조회 API 라우터 (/v1)

- GET /v1/inventory, GET /v1/inventory/{item_id}: 내 인벤토리 목록과 상세
- GET /v1/item-definitions, GET /v1/item-definitions/{definition_id}: 아이템 종류 목록과 상세
- 라우터는 입력 검증, 서비스 호출, 응답 변환만 한다 (업무 판정, DB 갱신, commit을 하지 않는다)
- 소유자 ID는 요청 값이 아니라 검증된 인증 정보에서 얻는다
- 이 도메인에서만 필요한 오류 핸들러(403 등)는 이 계층에서 정의하고 앱에 등록한다 (공통 오류는 팀 공통 핸들러가 처리한다)
"""

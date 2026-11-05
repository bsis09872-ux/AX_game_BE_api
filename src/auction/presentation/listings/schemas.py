# 요청
#   매물 등록: inventory_item_id 만 (판매자는 로그인 정보에서, 시작가는 서버가 결정)
#   입찰: amount (정수, 0보다 큼 — 형식 검증은 Pydantic, 금액 규칙은 엔티티)
#   목록 조회 쿼리: status, item_definition_id, page, size, 정렬
#
# 응답
#   매물 요약 (목록용): id, 아이템 이름, 현재가, 상태, ends_at
#   매물 상세: 위 + 판매자 이름, 시작가, 입찰자 존재 여부, started_at ...
#   거래: 스냅샷 필드들 + completed_at
#   → 입찰자 id를 공개할지 (개인정보) 확인 필요
# GET    /v1/listings                    목록 (필터 + 페이징)
# GET    /v1/listings/{listing_id}       상세
# POST   /v1/listings                    매물 등록        (로그인 필요)
# POST   /v1/listings/{listing_id}/bids  입찰             (로그인 필요)
# GET    /v1/trades/me                   내 거래 내역     (로그인 필요)
# (관리자) POST /v1/admin/listings/{id}/close  수동 마감 — 테스트용으로도 유용
#
# 로그인 사용자 정보는 auth 도메인이 제공하는 Depends로 받기
# 서비스 (작업 순서 지휘)

### 가능한 폴더 내 파일 구조
1. service.py
- 등록/입찰/시작/마감 흐름 지휘

# 생성자로 받는 것:
#   ListingRepository, TradeRepository
#   + 인벤토리 / 지갑 / 유저 쪽 기능 (각 도메인의 Repository 인터페이스 또는 Service)

# [매물 등록]
#   ① 인벤토리 아이템 조회 → 없으면 404
#   ② 소유자 == 요청자?            아니면 403
#   ③ 상태가 OWNED?                아니면 409
#   ④ resale_available_at 지났나?  아니면 400
#   ⑤ Listing 엔티티 생성 (QUEUED, start_price는 item_definitions에서)
#   ⑥ 인벤토리 아이템 → LISTED,  item_event(LISTED) 기록
#   ⑦ 같은 종류에 진행 중 매물이 없으면 바로 공개 시작? (대기열 정책, 확인 필요)

# [입찰]
#   ① 매물을 "잠금 조회"
#   ② 입찰자의 auction_blocked_until 확인 → 제한 중이면 403
#   ③ 엔티티의 입찰 메서드 호출 (규칙은 엔티티가 판단)
#   ④ 지갑: 새 입찰자 예약금 확보 / 직전 입찰자 예약금 해제
#       ("예약금 포함 총잔액"이라는 ERD 주석 → 예약 방식 설계 확인 필요)

# [마감] — 사용자 요청이 아니라 스케줄러(주기 작업)가 호출하는 기능
#   ① 마감 지난 BIDDING 매물을 잠금 조회
#   ② 엔티티 마감 메서드
#   ③ SOLD이면:
#       - 판매자·구매자 이름, 아이템 이름 조회 → Trade 생성 (스냅샷)
#       - 지갑: 구매자 → 판매자 금액 이동
#       - 인벤토리: 소유자 변경, 상태 OWNED, origin=TRADE, resale_available_at 설정
#       - item_event(TRANSFERRED) 기록 (listing_id, trade_id 포함)
#       - 구매자 auction_purchase_count 증가 (+ 제한 조건 넘으면 blocked_until 설정)
#   ④ FAILED이면:
#       - 인벤토리 아이템 → OWNED,  item_event(UNLISTED)
#   ⑤ 같은 종류의 다음 대기 매물 공개 시작


----
### 판단해야할 부분
- 낙찰 이후 거래 생성과 정산 요청을 조율 -> 상위 service 파일 별도로 두어야 하나? 각 애그리거트 안에서 해결?
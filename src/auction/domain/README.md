 # 엔티티, 규칙, Repository 인터페이스 (DB 모름)
 - Entity - 재료
 - Repository - 레시피/지시사항

 ### 가능한 폴더 내 파일 구조
 1. enums.py
 - 매물 상태: QUEUED / BIDDING / SOLD / FAILED 
 2. entities.py
 - listing, trade 엔티티 + 규칙 메서드
 3. repository.py
 - ListingRepository, TradeRepository 인터페이스

 --------

# 필드: ERD 컬럼과 동일 (id, 시간 필드는 기본값 None으로 뒤쪽에)
#
# [상태 전이] — 허용된 방향만 가능, 그 외는 예외
#   QUEUED  → BIDDING   (공개 시작)
#   BIDDING → SOLD      (입찰자 있음)
#   BIDDING → FAILED    (입찰자 없음)
#   SOLD / FAILED 는 종료 상태 → 더 이상 변경 불가
#
# [메서드: 공개 시작]
#   - QUEUED가 아니면 예외
#   - started_at = 지금, ends_at = 지금 + 경매 시간 (경매 시간은 설정값, 확인 필요)
#   - status = BIDDING
#
# [메서드: 입찰]
#   입력: 입찰자 id, 금액, 현재 시각
#   - BIDDING 아니면 예외
#   - 현재 시각 >= ends_at 이면 예외 (마감됨)
#   - 입찰자 == 판매자 → 예외 (자기 매물 입찰 금지)
#   - 첫 입찰: 금액 >= start_price
#     이후 입찰: 금액 > current_bid_amount (최소 증가 단위, 확인 필요)
#   - 같은 사람이 연속 최고 입찰 가능한지 (확인 필요)
#   - 통과 시 current_bidder_id, current_bid_amount 갱신
#   - 반환: "직전 최고 입찰자와 금액" → Service가 예약금 해제할 때 필요
#
# [메서드: 마감]
#   - BIDDING 아니면 예외, ends_at 전이면 예외
#   - 입찰자 있으면 SOLD, 없으면 FAILED
#   - closed_at = 지금
#
# 예외는 shared/core의 공통 예외 사용 (400 / 403 / 409 / 422)

---------------
#   - 낙찰된 Listing + 이름 정보들로 생성하는 "팩토리 메서드"
#   - Listing이 SOLD가 아니면 생성 불가
#   - 생성 후 변경 메서드 없음 (불변)


----------------
# ListingRepository
#   - id로 찾기
#   - id로 찾기 + "잠금" (입찰·마감처럼 동시에 수정될 수 있는 작업용, 아래 7번)
#   - 목록 조회 (상태 필터, 정렬, 페이징)
#   - 아이템 종류별 "다음 대기 매물" 1건 (QUEUED, created_at 오름차순)
#   - 아이템 종류별 "현재 진행 중 매물" 존재 여부
#   - 마감 시간이 지난 BIDDING 매물 목록
#   - 저장
#
# TradeRepository
#   - 저장
#   - listing_id로 찾기
#   - 구매자 id로 목록 (거래 내역)
"""
[Listing 엔티티 — 도메인 규칙]
DB·FastAPI를 모른다. 순수 Python만 사용한다.

■ 상태 (ListingStatus)
  QUEUED   대기열. 같은 item_definition의 BIDDING 매물이 있어서 등록순으로 기다림
  BIDDING  공개되어 입찰을 받는 중 (item_definition당 1개만)
  SOLD     낙찰 + 정산 성공 (종료)
  FAILED   입찰 없음 또는 정산 실패 (종료)

■ 상태 전이 — 허용된 방향만 가능, 그 외는 예외
  QUEUED  → BIDDING   공개 시작
  BIDDING → SOLD      입찰자 있음 + 정산 성공
  BIDDING → FAILED    입찰자 없음 또는 정산 실패
  SOLD / FAILED       종료 상태, 더 이상 변경 불가

■ 상수
  AUCTION_DURATION = 6분   (공개 후 입찰 가능 시간)

■ 필드 (ERD listings와 동일)
  inventory_item_id, item_definition_id, seller_id, current_bidder_id는
  다른 도메인의 ID 값만 저장한다. (FK 없음, 객체 참조 없음)
  id, 시간 필드는 기본값 None으로 뒤쪽에 둔다.

■ 생성 create(seller_id, inventory_item_id, item_definition_id, start_price, now)  — AUC-01
  - start_price > 0
  - status = QUEUED, created_at = now
  - 본인 소유 확인, 재판매 제한(AUC-09)은 여기서 하지 않는다.
    → inventory의 reserve_for_listing이 판단, 에러는 그대로 전달

■ 공개 시작 start(now)  — AUC-01, AUC-06
  - QUEUED가 아니면 예외
  - started_at = now, ends_at = now + AUCTION_DURATION
  - status = BIDDING

■ 입찰 place_bid(bidder_id, amount, now)  — AUC-04
  - BIDDING이 아니면 예외
  - now >= ends_at 이면 예외 (마감됨)
  - bidder_id == seller_id 이면 예외 (자기 매물 입찰 금지)
  - bidder_id == current_bidder_id 이면 예외 (본인 최고가 재입찰 금지)
  - 첫 입찰: amount > start_price  (시작가 "초과")
  - 이후 입찰: amount > current_bid_amount  (최소 증가액 없음)
  - 통과 시 current_bidder_id, current_bid_amount 갱신
  - 잔액 확인, 연속 낙찰 제한(AUC-08)은 여기서 하지 않는다. → Service 담당

■ 마감 판단  — AUC-05
  - is_expired(now): now >= ends_at
  - has_bidder(): current_bidder_id is not None

■ 종료 처리  — AUC-05
  - mark_sold(now)
      BIDDING이 아니면 예외, 마감 전이면 예외, 입찰자 없으면 예외
      status = SOLD, closed_at = now
  - mark_failed(now)
      BIDDING이 아니면 예외, 마감 전이면 예외
      status = FAILED, closed_at = now

■ 남은 시간 remaining(now)  — AUC-03
  - BIDDING일 때 max(ends_at - now, 0), 그 외 None

■ 예외
  shared/core 공통 예외 사용 (400 / 403 / 409 / 422)
  모든 now는 timezone 포함 UTC 값
"""


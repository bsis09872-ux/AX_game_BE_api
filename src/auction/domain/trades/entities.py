"""
[Trade 엔티티 — 도메인 규칙]
낙찰이 확정된 거래 기록. DB·FastAPI를 모른다.

■ 필드 (ERD trades와 동일)
  listing_id, seller_id, buyer_id,
  item_name_snapshot, seller_name_snapshot, buyer_name_snapshot,
  price_snapshot, completed_at
  - seller_id, buyer_id는 auction 컨텍스트의 역할 이름 (값은 users id, FK 없음)
  - snapshot은 체결 시점 값을 고정 저장

■ 생성 from_sold_listing(listing, item_name, seller_name, buyer_name, now)
  - listing.status != SOLD 이면 예외
  - seller_id = listing.seller_id
  - buyer_id = listing.current_bidder_id
  - price_snapshot = listing.current_bid_amount  (0보다 커야 함)
  - completed_at = now

■ 불변
  - 생성 후 변경 메서드 없음
  - 매물당 거래 1건 (listing_id UNIQUE, DB에서 한 번 더 보장)
"""

from shared.core import exceptions


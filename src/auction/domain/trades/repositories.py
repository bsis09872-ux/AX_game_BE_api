"""
[TradeRepository — 인터페이스(ABC)]
구현은 infrastructure/trades/repositories.py

■ 저장
  - save(trade) -> Trade

■ 조회
  - get_by_listing(listing_id) -> Trade | None
  - list_by_buyer(buyer_id, page) -> list[Trade]
      AUC-07 내 낙찰 내역, completed_at 최신순
  - list_by_seller(seller_id, page) -> list[Trade]
      AUC-10 내 판매 내역, completed_at 최신순
      조회 방식(seller_id 컬럼 or listings 조인)은 인프라가 결정한다.

■ 연속 낙찰 제한용  — AUC-08
  - recent_win_times(buyer_id, limit) -> list[datetime]
      최근 낙찰 시각 최신순 최대 limit개

■ DB 제약 (구현 시 반영)
  - UNIQUE (listing_id)
  - INDEX (buyer_id, completed_at)
"""
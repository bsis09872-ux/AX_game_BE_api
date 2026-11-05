"""
[ListingRepository — 인터페이스(ABC)]
무엇을 저장하고 찾을지만 정의한다. 구현은 infrastructure/listings/repositories.py

■ 조회
  - get(listing_id) -> Listing | None
  - get_for_update(listing_id) -> Listing | None
      행 잠금(FOR UPDATE). 입찰·마감처럼 동시에 수정될 수 있는 작업용
  - list_bidding(page) -> list[Listing]
      AUC-02 목록. BIDDING만 반환 (대기 매물은 서버가 숨김)

■ 대기열  — AUC-01, AUC-06
  - exists_bidding(item_definition_id) -> bool
      같은 종류의 공개 매물이 있는지
  - next_queued(item_definition_id) -> Listing | None
      같은 종류의 QUEUED 중 created_at이 가장 오래된 1건

■ 마감  — AUC-05
  - list_expired_bidding(now) -> list[Listing]
      BIDDING이고 ends_at <= now 인 매물

■ 입찰 가능 금액 계산  — AUC-04
  - sum_leading_bids(user_id) -> int
      user가 current_bidder_id인 BIDDING 매물들의 current_bid_amount 합

■ 저장
  - save(listing) -> Listing

■ DB 제약 (구현 시 반영)
  - UNIQUE (item_definition_id) WHERE status = 'BIDDING'
  - INDEX (item_definition_id, status, created_at)
  - INDEX (status, ends_at)
  - INDEX (current_bidder_id, status)
"""


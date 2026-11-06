# 등록·조회·입찰·취소 순서를 조율한다. 규칙 판단은 domain에 맡긴다.
# [TO DO] Repository와 inventory·wallet·사용자 제한 상태 인터페이스를 생성자로 받는다.
# [TO DO] 등록: 아이템 예약 → Listing.create → 같은 종류 공개 가능 여부 확인 → 저장.
# [TO DO] 시작가를 요청자가 정할지 서버가 정할지 합의한다. 현재 create는 인자로 받는다.
# [TO DO] 조회: 목록·상세를 반환한다. 제한 중인 사용자도 조회를 허용한다.
# [TO DO] 입찰: 사용자 제한 상태와 매물 잠금 → B 정책 판단 → 가용 잔액 확인 → place_bid → 저장.
# 가용 잔액은 잔액 - sum_leading_bids다. 별도 예약금 입출금 방식과 섞지 않는다.
# [TO DO] 제한 중이면 BusinessRuleError로 남은 시간을 안내한다. 현재 핸들러 기준 400이다.
# [TO DO] 취소: 잠금 조회 → cancel → inventory 예약 해제 → 저장을 같은 트랜잭션으로 처리한다.
# [TO DO] 같은 종류 공개 경쟁·동일 사용자 동시 입찰을 조율할 잠금 순서를 합의한다.
# [TO DO] page는 1부터, 공개 시각 최신순인 현재 Repository 계약과 page_size를 맞춘다.
# [TO DO] 외부 인터페이스는 application/constructs.py에 정의한다. 아직 생성되지 않았다.

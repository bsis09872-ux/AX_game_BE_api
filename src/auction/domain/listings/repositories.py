# 매물 저장·조회 Repository 인터페이스만 정의한다.
# 상세 계약: ../README.md → Repository 인터페이스 → ListingRepository
# 완료한 체크 항목은 테스트 확인 후 삭제하고 역할·README 안내는 유지한다.

# [ ] ListingRepository ABC 정의, 메서드별 입력·반환 타입 및 abstractmethod 선언
# [ ] get: 단건 조회, 없으면 None
# [ ] get_for_update: 수정 작업용 잠금 조회, 없으면 None
# [ ] list_bidding: 공개 중인 매물 목록
# [ ] exists_bidding: 같은 종류 공개 매물 존재 여부
# [ ] next_queued: 같은 종류의 가장 오래된 대기 매물
# [ ] list_expired_bidding: 마감 시각에 도달한 진행 매물
# [ ] sum_leading_bids: 사용자가 최고 입찰자인 진행 매물의 입찰액 합
# [ ] save: 매물 저장 및 엔티티 반환
# [ ] 목록 조회의 page 입력 계약을 application·infrastructure와 확인

# 책임 경계: SQL·잠금 실행·DB 제약·인덱스는 infrastructure에 구현한다.

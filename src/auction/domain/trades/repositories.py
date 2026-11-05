# 거래 기록 저장·조회 Repository 인터페이스만 정의한다.
# 상세 계약: ../README.md → Repository 인터페이스 → TradeRepository
# 완료한 체크 항목은 테스트 확인 후 삭제하고 역할·README 안내는 유지한다.

# [ ] TradeRepository ABC 정의, 메서드별 입력·반환 타입 및 abstractmethod 선언
# [ ] save: 저장된 ID가 반영된 Trade 반환
# [ ] get_by_listing: 매물의 거래 기록, 없으면 None
# [ ] list_by_buyer: 구매자의 낙찰 내역 최신순 조회
# [ ] list_by_seller: 판매자의 판매 내역 최신순 조회
# [ ] recent_win_times: 최근 낙찰 시각 최신순으로 최대 limit개 반환
# [ ] 목록 조회의 page 입력 계약을 application·infrastructure와 확인

# 책임 경계: SQL·DB 제약·인덱스는 infrastructure에 구현한다.
# 저장 ID 반영은 README의 dataclasses.replace 기준을 따른다.

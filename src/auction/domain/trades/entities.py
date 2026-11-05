# 낙찰이 확정된 거래를 변경 불가능한 기록으로 보존한다.
# 상세 규칙: ../README.md → Trade, 공통 규칙, 예외
# 완료한 체크 항목은 테스트 확인 후 삭제하고 역할·README 안내는 유지한다.

# [ ] Trade: README 필드 표에 맞춰 frozen dataclass 정의 (저장 전 id=None)
# [ ] from_sold_listing: SOLD 상태와 필수 값 누락 검증
# [ ] 양수 낙찰가·시간 입력 규칙 검증
# [ ] 판매자·구매자·낙찰가·이름 스냅샷·체결 시각 저장
# [ ] 테스트: 확정 매물의 값과 스냅샷이 정확히 복사되는지 확인
# [ ] 테스트: 잘못된 상태·필수 값 누락·유효하지 않은 낙찰가 거부
# [ ] 테스트: 생성 후 필드 변경 불가 확인

# 책임 경계: 정산은 application, 매물당 거래 1건의 DB 제약은 infrastructure.


from shared.core import exceptions


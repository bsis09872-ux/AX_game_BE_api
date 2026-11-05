# 매물의 생성·입찰·상태 전이 규칙을 담당한다.
# 상세 규칙: ../README.md → Listing, 공통 규칙, 예외
# 완료한 체크 항목은 테스트 확인 후 삭제하고 역할·README 안내는 유지한다.

# [ ] ListingStatus: QUEUED / BIDDING / SOLD / FAILED 정의
# [ ] AUCTION_DURATION(6분), _ALLOWED_TRANSITIONS 정의
# [ ] Listing dataclass: README 필드 표 적용 (필수 필드 먼저, 기본값 필드 뒤)
# [ ] _ensure_aware: 시간 입력 규칙 검증
# [ ] _require_status: 현재 상태 검증
# [ ] _transition_to: 허용된 전이만 수행하고 updated_at = now 갱신
# [ ] create — AUC-01: 시작가 검증 후 QUEUED 생성, created_at·updated_at = now
# [ ] start — AUC-01, AUC-06: 공개·마감 시각 설정 후 _transition_to로 전환
# [ ] place_bid — AUC-04: README 검사 순서·예외 코드 적용
#     모든 검사 통과 후 최고 입찰자·입찰액 변경, 메서드 안에서 updated_at = now
# [ ] is_expired — AUC-05: return self.ends_at is not None and now >= self.ends_at
#     ends_at=None이면 예외 없이 False 반환
# [ ] has_bidder — AUC-05: 입찰자 존재 여부 반환
# [ ] remaining — AUC-03: 진행 중 남은 시간, 그 외 None 반환
# [ ] mark_sold — AUC-05: 마감·입찰자 확인 후 SOLD 전환 및 종료 시각 기록
# [ ] mark_failed — AUC-05: 마감 확인 후 FAILED 전환 및 종료 시각 기록
# [ ] 테스트: 정상·금지 전이, 마감 정각, 입찰 금액 경계
# [ ] 테스트: ends_at=None의 is_expired는 False
# [ ] 테스트: 성공한 5개 행위의 updated_at 갱신, 조회·실패 시 기존 값 유지

# 책임 경계: 소유권·재판매 제한은 inventory, 잔액 확인·정산 조율은 application.
# updated_at은 DB onupdate에 맡기지 않고 도메인의 now로 설정한다.

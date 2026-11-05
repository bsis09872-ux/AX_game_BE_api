# 최근 낙찰 시각으로 새 입찰 제한 여부를 판단하는 순수 함수를 둔다.
# 상세 규칙: ../README.md → 정책
# 완료한 체크 항목은 테스트 확인 후 삭제하고 역할·README 안내는 유지한다.

# [ ] WIN_LIMIT_COUNT=3, WIN_LIMIT_WINDOW=30분, BID_BAN_DURATION=10분 정의
# [ ] is_bid_banned(recent_win_times, now) -> bool 구현
#     입력: 최근 낙찰 시각 최신순, 최대 WIN_LIMIT_COUNT개
#     기준 건수 미만이면 False, 그 외 README의 낙찰 간격·제한 종료 조건 적용
# [ ] 테스트: 기록 없음·기준 건수 미만, 낙찰 간격 30분 정각·초과
# [ ] 테스트: 마지막 낙찰부터 10분의 종료 직전·정각·이후
# [ ] 테스트: 입력 목록을 변경하지 않는지 확인

# 책임 경계: 조회는 허용하고 새 입찰만 제한하며, 제한 전 입찰의 낙찰은 막지 않는다.
# DB 조회와 BID_BANNED 예외 발생은 application 담당. 함수는 판단 결과만 반환한다.

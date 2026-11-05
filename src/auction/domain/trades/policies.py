# 최근 낙찰 시각으로 새 입찰 제한 여부를 판단하는 순수 함수를 둔다.

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

from datetime import datetime, timedelta


# 1. 연속 낙찰 제한 기준
WIN_LIMIT_COUNT = 3
WIN_LIMIT_WINDOW = timedelta(minutes=30)
BID_BAN_DURATION = timedelta(minutes=10)


# 2. [AUC-08] 새 입찰을 받기 전에 최근 낙찰 기록으로 입찰 제한 여부를 판단한다.
def is_bid_banned(recent_win_times: list[datetime], now: datetime) -> bool:
    # 입력은 최신순으로 조회한 최근 낙찰 시각 최대 3개다.
    _ensure_aware(now)
    for win_time in recent_win_times:
        _ensure_aware(win_time)

    if len(recent_win_times) < WIN_LIMIT_COUNT:
        return False

    latest_win = recent_win_times[0]
    third_latest_win = recent_win_times[WIN_LIMIT_COUNT - 1]

    within_window = latest_win - third_latest_win <= WIN_LIMIT_WINDOW
    ban_not_over = now < latest_win + BID_BAN_DURATION

    return within_window and ban_not_over


# 3. 시간 차이를 계산하기 전에 UTC 시각인지 확인한다. 
# 도메인 내부에서도 잘못된 입력을 막기 위함 - 필수는 아니라 고민
def _ensure_aware(value: datetime) -> None:
    offset = value.utcoffset()

    if offset is None:
        raise ValueError("시각에는 시간대 정보가 필요합니다.")
    if offset != timedelta(0):
        raise ValueError("시각은 UTC여야 합니다.")
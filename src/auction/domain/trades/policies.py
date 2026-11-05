"""
[거래 기록 기반 정책 — 순수 함수]
엔티티 하나로는 판단할 수 없는 규칙. 입력은 시각 값만 받는다.

■ 상수
  WIN_LIMIT_COUNT  = 3        이 횟수 이상 낙찰하면
  WIN_LIMIT_WINDOW = 30분     이 시간 안에
  BID_BAN_DURATION = 10분     이 시간 동안 새 입찰 금지  🟨 15~18분 검토

■ is_bid_banned(recent_win_times, now) -> bool  — AUC-08
  - recent_win_times: 최근 낙찰 시각 최신순 (최대 WIN_LIMIT_COUNT개)
  - 개수 < WIN_LIMIT_COUNT 이면 False
  - (가장 최근 - WIN_LIMIT_COUNT번째) <= WIN_LIMIT_WINDOW 이고
    now < 가장 최근 + BID_BAN_DURATION 이면 True
  - 새 입찰만 막는다. 제한 전에 해 둔 입찰의 낙찰은 막지 않는다.
  - 호출 위치: application/listings/service.py 입찰 흐름
"""
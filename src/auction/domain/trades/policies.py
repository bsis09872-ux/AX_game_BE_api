# 낙찰 기록과 이전 차단 종료 시각으로 입찰 제한 상태를 계산한다.
# get_limit_state: 조회·입찰 검사 시 현재 상태만 계산한다.
# calculate_limit_after_win: 이번 낙찰 포함 최근 30분 내 3회 낙찰이면,
# 이번 낙찰 시각부터 15분간 새 입찰을 제한한다.
# 경매장 입장·조회와 기존 입찰의 낙찰·정산은 허용한다.
# 만료된 blocked_until은 이전 집계 주기를 제외하는 기준이므로 보존한다.
# 차단 중 추가 낙찰은 종료 시각을 연장하지 않으며 표시 횟수는 3/3이다.
#
# [TO DO] 30분 경계·차단 종료 정각·초기화 후 새 낙찰 집계를 테스트한다.
# [TO DO] 차단 중 추가 낙찰의 비연장과 입력 기록이 변경되지 않는지 테스트한다.
# DB 조회·User 상태 저장·동시 처리 조율·업무 예외 발생은 application에서 연결한다.

from dataclasses import dataclass
from datetime import datetime, timedelta

# 낙찰 횟수 기준, 과거 기록 집계 범위, 새 입찰 제한 기간
WIN_LIMIT_COUNT = 3
WIN_LIMIT_WINDOW = timedelta(minutes=30)
BID_BAN_DURATION = timedelta(minutes=15)


# 사용자의 현재 경매 입찰 제한 상태를 담는 계산 결과다.
# application이 이 결과로 User 저장값을 갱신하거나 응답을 만든다.
# frozen=True이므로 결과를 만든 뒤 필드 값을 변경할 수 없다.
@dataclass(frozen=True)
class AuctionLimitState:
    purchase_count: int                 # 현재 유효 낙찰 횟수. 차단 중에는 3으로 표시
    blocked_until: datetime | None      # 차단 종료 시각. 만료 후에도 집계 기준으로 보존
    is_blocked: bool                    # 현재 새 입찰이 제한되는지
    remaining: timedelta                # 제한 해제까지 남은 시간. 해제 상태면 0
    max_count: int = WIN_LIMIT_COUNT     # 제한 발동 기준인 최대 횟수


# 참여 상태를 조회하거나 새 입찰을 검사할 때 현재 제한 상태를 계산한다.
# DB를 조회하거나 값을 저장하지 않으며, 조회만으로 새 차단을 발동하지 않는다.
#
# win_times: 집계에 필요한 낙찰 시각 목록. 최신 3건이 아닌 기간 내 전체 기록을 받는다.
# blocked_until: User에 저장된 차단 종료 시각. 만료됐더라도 None으로 지우지 않는다.
# now: 이번 판단의 기준 시각. timezone-aware UTC 값으로 전달한다.
def get_limit_state(
    win_times: list[datetime],
    blocked_until: datetime | None,
    now: datetime,
) -> AuctionLimitState:
    _validate_utc_time(now)

    if blocked_until is not None:
        _validate_utc_time(blocked_until)

    for win_time in win_times:
        _validate_utc_time(win_time)

    # 제한 중에는 3/3으로 표시하고 기존 종료 시각을 유지한다.
    # 추가 낙찰 기록이 들어와도 여기서는 제한 시간을 연장하지 않는다.
    if blocked_until is not None and now < blocked_until:
        return AuctionLimitState(
            purchase_count=WIN_LIMIT_COUNT,
            blocked_until=blocked_until,
            is_blocked=True,
            remaining=blocked_until - now,
        )

    # 기본 집계 범위는 최근 30분이다.
    # 이전 차단이 끝났다면 그 종료 시각 이전의 기록도 제외한다.
    since = now - WIN_LIMIT_WINDOW
    if blocked_until is not None:
        since = max(since, blocked_until)

    # 시작·종료 경계를 포함한다.
    # 같은 시각에 발생한 서로 다른 거래도 각각 한 건으로 센다.
    purchase_count = sum(
        1 for win_time in win_times
        if since <= win_time <= now
    )

    # 만료된 종료 시각을 보존해야 다음 계산에서도 이전 주기를 제외할 수 있다.
    return AuctionLimitState(
        purchase_count=purchase_count,
        blocked_until=blocked_until,
        is_blocked=False,
        remaining=timedelta(0),
    )


# 이번 낙찰을 포함해 최근 30분 내 유효 낙찰이 3건이면 15분간 새 입찰을 제한한다.
# 이전 차단 종료 전의 기록은 제외하며, 제한 중 추가 낙찰은 종료 시각을 연장하지 않는다.
# 단순 조회나 입찰 요청에서는 호출하지 않고, 새 낙찰 확정 시에만 호출한다.
#
# win_times에는 이번 Trade의 낙찰 시각이 정확히 한 번 포함되어야 한다.
# now에는 이번 Trade.completed_at을 전달한다.
# application은 사용자별 처리를 잠금으로 순서대로 진행하고 결과를 저장한다.
def calculate_limit_after_win(
    win_times: list[datetime],
    blocked_until: datetime | None,
    now: datetime,
) -> AuctionLimitState:
    state = get_limit_state(win_times, blocked_until, now)

    # 차단 전에 접수된 입찰이 추가로 낙찰돼도 기존 차단을 연장하지 않는다.
    # 거래 정산 자체의 허용 여부는 이 함수에서 검사하지 않는다.
    if state.is_blocked:
        return state

    # 최근 유효 낙찰이 3건 미만이면 집계 결과만 반환한다.
    if state.purchase_count < WIN_LIMIT_COUNT:
        return state

    # 정상적인 순차 처리에서는 이번 세 번째 낙찰로 이 분기에 도달한다.
    # 거래 기록에서 전달받은 체결 시각(completed_at)부터 15분 을 계산한다.
    return AuctionLimitState(
        purchase_count=WIN_LIMIT_COUNT,
        blocked_until=now + BID_BAN_DURATION,
        is_blocked=True,
        remaining=BID_BAN_DURATION,
    )


# 시간 비교 전에 timezone 정보와 UTC 여부를 검사하는 내부 보조 함수다.
# 시간을 UTC로 변환하지 않는다. 올바르지 않은 입력은 ValueError로 알린다.
def _validate_utc_time(value: datetime) -> None:
    offset = value.utcoffset()

    if offset is None:
        raise ValueError("시각에는 시간대 정보가 필요합니다.")

    if offset != timedelta(0):
        raise ValueError("시각은 UTC여야 합니다.")
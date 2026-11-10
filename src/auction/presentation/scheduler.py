# Scheduler: 일정 간격으로 마감 시각이 지난 경매를 종료한다.
# 요청 밖에서 실행되므로 주기마다 새 세션으로 서비스를 열고 닫는다.
# 업무 규칙과 트랜잭션은 AuctionService가 담당하고, 여기서는 실행 시점만 정한다.
# 여러 서버에서 동시에 실행돼도 매물 잠금 후 상태를 다시 확인하므로 같은 매물을 두 번 정산하지 않는다.

import asyncio
import contextlib
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timezone
from typing import Protocol

logger = logging.getLogger(__name__)


# 스케줄러가 호출하는 마감 기능의 계약이다. (AuctionService.close_expired)
class ExpiredAuctionCloser(Protocol):
    async def close_expired(self, now: datetime) -> int:
        ...


# 주기마다 마감 서비스를 열어 주는 함수의 형태다. wiring의 open_auction_service가 해당한다.
OpenCloser = Callable[[], AbstractAsyncContextManager[ExpiredAuctionCloser]]


class AuctionCloseScheduler:
    # 입력: 서비스를 여는 함수와 실행 간격(초). 생성만 하고 실행은 start에서 시작한다.
    def __init__(self, open_closer: OpenCloser, interval_seconds: float) -> None:
        if interval_seconds <= 0:
            raise ValueError("실행 간격은 0보다 커야 합니다.")
        self._open_closer = open_closer
        self._interval = interval_seconds
        self._task: asyncio.Task[None] | None = None

    # 백그라운드 반복 작업을 시작한다. 이미 실행 중이면 새로 만들지 않는다.
    # 반환값 없음. 실행 중인 이벤트 루프 안(앱 lifespan)에서 호출한다.
    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(
                self._run(),
                name="auction-close-scheduler",
            )

    # 반복 작업을 취소하고 끝날 때까지 기다린다.
    # 처리 중이던 매물은 commit 전이면 세션이 닫히며 rollback되고, 다음 실행 때 다시 처리된다.
    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    # 한 번 실행: 새 세션으로 서비스를 열고 현재 UTC 시각 기준으로 마감 처리한다.
    # 반환: 이번 실행에서 종료한 매물 수. 검증할 때 직접 호출할 수 있다.
    async def run_once(self) -> int:
        async with self._open_closer() as closer:
            return await closer.close_expired(datetime.now(timezone.utc))

    # 간격마다 run_once를 반복한다.
    # 실패해도 로그만 남기고 다음 주기에 다시 시도한다. 취소(CancelledError)는 잡지 않고 종료한다.
    async def _run(self) -> None:
        while True:
            try:
                closed = await self.run_once()
                if closed:
                    logger.info("경매 마감 처리: %s건", closed)
            except Exception:
                logger.exception("경매 마감 주기 실행 실패")
            await asyncio.sleep(self._interval)

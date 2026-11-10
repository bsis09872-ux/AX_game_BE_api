// [Claude] 이 파일은 Claude가 작성함 (검토 전)
// 경매 상세 화면의 실시간 반영.
// - 남은 시간과 진행 바: 서버가 준 남은 초를 기준으로 브라우저가 1초마다 직접 센다 (서버에 묻지 않는다)
// - 가격, 최고 입찰자, 낙찰·유찰·취소: 몇 초마다 작은 상태 주소를 확인(폴링)하고, 달라졌으면 같은 화면을 다시 불러온다
// pages.js에 page_key "auction"으로 등록되어 화면이 바뀔 때마다 한 번 호출된다 (docs/project-structure.md)

const POLL_MS = 2000; // 평소 확인 간격
const CLOSING_POLL_MS = 1000; // 시간이 끝나고 정산을 기다리는 동안 확인 간격
const RETRY_MS = 3000; // 화면을 다시 불러오지 못했을 때 다시 시도하기까지
const URGENT_SECONDS = 60; // 이 시간 이하면 급한 색 (web_views.py의 URGENT_SECONDS와 같다)

// 입력 중이던 입찰 금액을 화면을 다시 불러온 뒤에도 남기려고 잠시 들고 있는다
let carried = null;

export function formatClock(seconds) {
    const total = Math.max(0, seconds);
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export function initAuctionLive({ root, signal, navigate }) {
    const live = root.querySelector("[data-auction-live]");
    if (!live) {
        return;
    }

    const stateUrl = live.dataset.stateUrl;
    const listingId = live.dataset.listingId;
    const initial = {
        status: live.dataset.status,
        price: Number(live.dataset.price),
        leader: live.dataset.leader,
    };
    const total = Number(live.dataset.total) || 0;
    const clock = root.querySelector("[data-live-clock]");
    const timeLine = root.querySelector("[data-live-time]");
    const bar = root.querySelector("[data-live-bar]");
    const fill = root.querySelector("[data-live-fill]");
    const form = root.querySelector(".bid-form");
    const input = root.querySelector("#bid-amount");
    const bubble = root.querySelector(".bid-message");

    // 화면을 다시 불러오기 전에 입력하던 금액이 있으면, 새 최소 금액 이상일 때만 되살린다
    if (carried && carried.listingId === listingId && input) {
        const typed = Number(carried.value);
        if (Number.isFinite(typed) && typed >= Number(input.min)) {
            input.value = carried.value;
        }
    }
    carried = null;

    let remaining = Number(live.dataset.remaining);
    let baseline = performance.now();
    let pollTimer = null;
    let tickTimer = null;
    let busy = false;
    let stopped = false;
    let closedShown = false;

    // 서버가 알려 준 남은 초에서 지난 시간을 빼서 지금 남은 초를 구한다
    function secondsLeft() {
        return Math.max(0, remaining - Math.floor((performance.now() - baseline) / 1000));
    }

    function showClosing() {
        if (closedShown) {
            return;
        }
        closedShown = true;
        if (timeLine) {
            timeLine.textContent = "경매 마감 (정산 중)";
        }
        if (fill) {
            fill.style.width = "0%";
        }
        // 시간이 끝났으니 입찰할 수 없다 (서버도 거절한다)
        form?.querySelectorAll("input, button").forEach((control) => {
            control.disabled = true;
        });
        if (bubble) {
            bubble.textContent = "경매 시간이 끝났어요. 곧 결과가 나와요.";
        }
    }

    function render() {
        if (initial.status !== "BIDDING") {
            return;
        }
        const left = secondsLeft();
        if (left <= 0) {
            showClosing();
            return;
        }
        const urgent = left <= URGENT_SECONDS;
        if (clock) {
            clock.textContent = formatClock(left);
            clock.classList.toggle("urgent", urgent);
        }
        if (bar && fill && total > 0) {
            fill.style.width = `${Math.min(100, (left / total) * 100).toFixed(2)}%`;
            bar.classList.toggle("urgent", urgent);
            bar.setAttribute("aria-valuenow", String(left));
            bar.setAttribute("aria-valuetext", `경매 마감까지 ${formatClock(left)}`);
        }
    }

    function stop() {
        stopped = true;
        clearTimeout(pollTimer);
        clearInterval(tickTimer);
    }

    function schedule(delay) {
        clearTimeout(pollTimer);
        // 탭이 가려져 있으면 확인하지 않는다. 다시 보이면 visibilitychange에서 바로 확인한다
        if (stopped || signal.aborted || document.hidden) {
            return;
        }
        pollTimer = setTimeout(poll, delay);
    }

    // 같은 주소를 다시 불러와 화면을 최신 상태로 바꾼다 (공통 페이지 전환을 쓴다)
    async function refresh() {
        stop();
        if (input && input.value !== input.defaultValue) {
            carried = { listingId, value: input.value };
        }
        await navigate(location.href, { replace: true });

        // 화면이 바뀌었으면 이 함수는 signal로 정리됐다. 못 바꿨으면 잠시 뒤 다시 확인한다
        if (!signal.aborted) {
            stopped = false;
            tickTimer = setInterval(render, 1000);
            schedule(RETRY_MS);
        }
    }

    async function poll() {
        if (stopped || busy || signal.aborted) {
            return;
        }
        busy = true;
        let changed = false;
        try {
            const response = await fetch(stateUrl, {
                credentials: "same-origin",
                cache: "no-store",
                signal,
            });
            if (response.status === 404 || response.status === 401) {
                // 사라졌거나 로그인이 풀렸다. 화면을 다시 불러오면 서버가 알맞은 화면을 보여 준다
                changed = true;
            } else if (response.ok) {
                const state = await response.json();
                changed =
                    state.status !== initial.status ||
                    state.price !== initial.price ||
                    state.leader !== initial.leader;
                if (!changed) {
                    // 남은 시간을 서버 기준으로 다시 맞춘다 (오래 켜 두면 생기는 오차를 없앤다)
                    remaining = state.remaining;
                    baseline = performance.now();
                }
            }
        } catch {
            // 통신 실패는 조용히 넘기고 다음 주기에 다시 확인한다
        } finally {
            busy = false;
        }

        if (signal.aborted) {
            return;
        }
        if (changed) {
            await refresh();
            return;
        }
        schedule(initial.status === "BIDDING" && secondsLeft() <= 0 ? CLOSING_POLL_MS : POLL_MS);
    }

    function onVisibility() {
        if (!document.hidden) {
            void poll();
        }
    }

    signal.addEventListener("abort", stop, { once: true });
    document.addEventListener("visibilitychange", onVisibility, { signal });

    render();
    tickTimer = setInterval(render, 1000);
    schedule(POLL_MS);
}

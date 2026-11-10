// [Claude] 이 파일은 Claude가 작성함 (검토 전)
// 경매·가방 화면의 실시간 반영. pages.js에 등록되어 화면이 바뀔 때마다 한 번 호출된다 (docs/project-structure.md)
// - 경매 상세: 남은 시간은 서버가 준 남은 초로 브라우저가 1초마다 직접 세고, 가격·최고 입찰자·결과는 작은 상태 주소를 몇 초마다 확인(폴링)한다
// - 경매 목록: 카드의 남은 시간을 직접 세고, 몇 초마다 목록을 다시 읽어 바뀐 카드만 깜빡이며 갈아 끼운다 (검색 입력은 건드리지 않는다)
// - 내 거래·가방: 탭이 다시 보일 때 한 번 다시 읽어 표시를 최신으로 맞춘다

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

function initDetailLive({ root, signal, navigate }) {
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

const LIST_POLL_MS = 5000; // 목록을 다시 읽는 간격
const FLASH_MS = 1300; // 바뀐 카드가 깜빡이는 시간
const REFRESH_GAP_MS = 5000; // 탭이 다시 보일 때, 마지막 확인 뒤 이만큼 지났을 때만 다시 읽는다

// 같은 주소를 다시 읽어 HTML 문서로 돌려준다. 못 읽거나 다른 화면이면 null
async function fetchPage(signal) {
    try {
        const response = await fetch(location.href, {
            credentials: "same-origin",
            cache: "no-store",
            signal,
        });
        if (!response.ok) {
            return null;
        }
        return new DOMParser().parseFromString(await response.text(), "text/html");
    } catch {
        return null;
    }
}

// 경매 목록: 카드의 남은 시간을 매초 세고, 목록은 몇 초마다 다시 읽어 바뀐 카드만 갈아 끼운다
function initListLive({ root, signal }) {
    const region = root.querySelector("[data-live-list]");
    if (!region) {
        return;
    }

    let clocks = [];
    let busy = false;
    let pollTimer = null;
    let tickTimer = null;
    const flashTimers = new Set();

    // 카드마다 서버가 준 남은 초와 받은 시각을 기억한다
    function collectClocks() {
        const now = performance.now();
        clocks = [...region.querySelectorAll("[data-live-seconds]")].map((element) => ({
            element,
            seconds: Number(element.dataset.liveSeconds),
            at: now,
        }));
    }

    function renderClocks() {
        const now = performance.now();
        for (const clock of clocks) {
            const left = Math.max(0, clock.seconds - Math.floor((now - clock.at) / 1000));
            clock.element.textContent = left > 0 ? formatClock(left) : "마감";
            clock.element.classList.toggle("urgent", left <= URGENT_SECONDS);
        }
    }

    // 카드 표시: "번호:가격:입찰자 있음" 모음. 달라졌는지 비교하는 데 쓴다
    function signatures(scope) {
        const map = new Map();
        for (const card of scope.querySelectorAll("[data-sig]")) {
            map.set(card.dataset.sig.split(":")[0], card.dataset.sig);
        }
        return map;
    }

    function schedule() {
        clearTimeout(pollTimer);
        if (signal.aborted || document.hidden) {
            return;
        }
        pollTimer = setTimeout(poll, LIST_POLL_MS);
    }

    async function poll() {
        if (busy || signal.aborted) {
            return;
        }
        busy = true;
        const next = await fetchPage(signal);
        busy = false;
        if (signal.aborted) {
            return;
        }

        const nextRegion = next?.querySelector("[data-live-list]");
        if (nextRegion) {
            const before = signatures(region);
            const after = signatures(nextRegion);
            const changed =
                before.size !== after.size || [...after].some(([id, sig]) => before.get(id) !== sig);

            if (changed) {
                region.replaceChildren(...nextRegion.childNodes);
                const count = root.querySelector("[data-live-count]");
                const nextCount = next.querySelector("[data-live-count]");
                if (count && nextCount) {
                    count.textContent = nextCount.textContent;
                }
                collectClocks();
                // 새로 생겼거나 값이 바뀐 카드를 잠깐 깜빡인다
                for (const card of region.querySelectorAll("[data-sig]")) {
                    const id = card.dataset.sig.split(":")[0];
                    if (before.get(id) !== card.dataset.sig) {
                        card.classList.add("flash");
                        const timer = setTimeout(() => {
                            card.classList.remove("flash");
                            flashTimers.delete(timer);
                        }, FLASH_MS);
                        flashTimers.add(timer);
                    }
                }
            } else {
                // 달라진 게 없으면 남은 시간만 서버 기준으로 다시 맞춘다
                const seconds = new Map(
                    [...nextRegion.querySelectorAll("[data-sig]")].map((card) => [
                        card.dataset.sig.split(":")[0],
                        Number(card.querySelector("[data-live-seconds]")?.dataset.liveSeconds),
                    ]),
                );
                const now = performance.now();
                for (const card of region.querySelectorAll("[data-sig]")) {
                    const fresh = seconds.get(card.dataset.sig.split(":")[0]);
                    const clock = clocks.find((item) => card.contains(item.element));
                    if (clock && Number.isFinite(fresh)) {
                        clock.seconds = fresh;
                        clock.at = now;
                    }
                }
            }
        }
        schedule();
    }

    function onVisibility() {
        if (!document.hidden) {
            void poll();
        }
    }

    signal.addEventListener(
        "abort",
        () => {
            clearTimeout(pollTimer);
            clearInterval(tickTimer);
            flashTimers.forEach(clearTimeout);
        },
        { once: true },
    );
    document.addEventListener("visibilitychange", onVisibility, { signal });

    collectClocks();
    renderClocks();
    tickTimer = setInterval(renderClocks, 1000);
    schedule();
}

// 탭이 다시 보일 때 지정한 영역만 다시 읽어 최신으로 맞춘다 (내 거래, 가방)
function refreshOnReturn({ root, signal }) {
    const region = root.querySelector("[data-live-refresh]");
    if (!region) {
        return;
    }

    let lastCheck = performance.now();
    let busy = false;

    async function onVisibility() {
        if (document.hidden || busy || performance.now() - lastCheck < REFRESH_GAP_MS) {
            return;
        }
        busy = true;
        const next = await fetchPage(signal);
        busy = false;
        lastCheck = performance.now();

        const nextRegion = next?.querySelector("[data-live-refresh]");
        if (!signal.aborted && nextRegion && region.innerHTML !== nextRegion.innerHTML) {
            region.replaceChildren(...nextRegion.childNodes);
        }
    }

    document.addEventListener("visibilitychange", onVisibility, { signal });
}

// 경매 화면(page_key "auction")에서 호출된다
export function initAuctionLive(context) {
    initDetailLive(context);
    initListLive(context);
    refreshOnReturn(context);
}

// 가방·도감 화면(page_key "inventory")에서 호출된다
export function initInventoryLive(context) {
    refreshOnReturn(context);
}

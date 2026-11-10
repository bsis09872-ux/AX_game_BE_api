// 보유 아이템 이력 조회와 페이지 이동을 담당한다.
export function initItemEvents(context) {
    const { getElement, request, appendCell, updatePagination, run } = context;
    if (!getElement("event-search")) {
        return;
    }

    let eventPage = 1;
    let eventItem = null;
    let eventRequest = 0;

    async function loadEvents() {
        const requestId = ++eventRequest;
        getElement("event-rows").replaceChildren();
        getElement("event-page").textContent = "조회 중...";

        getElement("event-prev").disabled = getElement("event-next").disabled = true;
        try {
            const result = await request(
                `/admin/inventory/${encodeURIComponent(eventItem)}/events?page=${eventPage}&size=20`,
            );
            if (requestId !== eventRequest) return;
            for (const item of result.items) {
                const row = document.createElement("tr");
                for (const value of [
                    new Date(item.created_at)
                        .toISOString()
                        .replace("T", " ")
                        .replace(/\.\d{3}Z$/, " UTC"),
                    item.event_type,
                    item.from_owner_id,
                    item.to_owner_id,
                    item.actor_id,
                    `${item.listing_id ?? "—"} / ${item.trade_id ?? "—"}`,
                ])
                    appendCell(row, value);
                getElement("event-rows").append(row);
            }
            if (!result.items.length) {
                const row = document.createElement("tr");
                appendCell(row, "기록된 이력이 없습니다.").colSpan = 6;
                getElement("event-rows").append(row);
            }

            updatePagination("event", result);
        } catch (error) {
            if (requestId === eventRequest) getElement("event-page").textContent = "조회 실패";
            throw error;
        }
    }

    // 입력 이벤트는 이 화면의 요소에만 연결한다.
    getElement("event-search").addEventListener("submit", (event) => {
        event.preventDefault();
        eventItem = event.target.elements.item_id.value;
        eventPage = 1;
        run(loadEvents);
    });

    getElement("event-prev").addEventListener("click", () => {
        eventPage--;
        run(loadEvents);
    });

    getElement("event-next").addEventListener("click", () => {
        eventPage++;
        run(loadEvents);
    });
    const itemId = new URLSearchParams(location.search).get("item_id");
    if (itemId && /^[1-9]\d{0,18}$/.test(itemId) && BigInt(itemId) <= 9223372036854775807n) {
        getElement("event-search").elements.item_id.value = itemId;
        eventItem = itemId;
        run(loadEvents);
    }
}

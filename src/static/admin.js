(() => {
    "use strict";
    const $ = id => document.getElementById(id);
    const editor = $("catalog-editor");
    let editingId = null, catalogPage = 1, eventPage = 1, eventItem = null;
    let catalogRequest = 0, eventRequest = 0;

    function message(text, error = false) {
        $("admin-message").textContent = text;
        $("admin-message").dataset.error = String(error);
    }

    async function request(path, options = {}) {
        const response = await fetch(path, {credentials:"same-origin", cache:"no-store", ...options});
        if (response.redirected || response.status === 401) {
            location.replace("/login?expired=1");
            throw new Error("다시 로그인해 주세요.");
        }
        if (response.status === 204) return null;
        const data = await response.json();
        if (!response.ok) {
            const detail = data.detail;
            throw new Error(Array.isArray(detail) ? "입력 형식과 값을 확인해 주세요." :
                detail?.message || (typeof detail === "string" ? detail : "요청을 처리하지 못했습니다."));
        }
        return data;
    }

    function cell(row, text) {
        const node = document.createElement("td");
        node.textContent = text ?? "—";
        row.append(node);
        return node;
    }

    function pagination(prefix, result) {
        $(prefix + "-page").textContent = `${result.page} / ${Math.max(1, Math.ceil(result.total / result.size))} 페이지, ${result.total}건`;
        $(prefix + "-prev").disabled = result.page <= 1;
        $(prefix + "-next").disabled = result.page * result.size >= result.total;
    }

    function resetEditor() {
        editingId = null;
        editor.reset();
        for (const name of ["code", "name", "category", "rarity"]) editor.elements[name].disabled = false;
        $("editor-title").textContent = "카탈로그 추가";
        $("save-catalog").textContent = "추가";
    }

    function edit(row) {
        resetEditor();
        editingId = row.id;
        for (const [key, value] of Object.entries(row)) {
            const input = editor.elements[key];
            if (!input) continue;
            if (input.type === "checkbox") input.checked = value;
            else input.value = value;
        }
        for (const name of ["code", "name", "category", "rarity"]) editor.elements[name].disabled = true;
        $("editor-title").textContent = `${row.name} 수정`;
        $("save-catalog").textContent = "변경 저장";
        editor.elements.start_price.focus();
    }

    async function loadCatalog() {
        const serial = ++catalogRequest;
        const params = new URLSearchParams(new FormData($("catalog-filters")));
        for (const key of ["category", "rarity"]) if (!params.get(key)) params.delete(key);
        params.set("page", catalogPage);
        params.set("size", 20);
        const result = await request("/admin/item-catalogs?" + params);
        if (serial !== catalogRequest) return;
        if (!result.items.length && catalogPage > 1) { catalogPage--; return loadCatalog(); }
        $("catalog-rows").replaceChildren();
        for (const item of result.items) {
            const row = document.createElement("tr");
            cell(row, item.id); cell(row, `${item.name} / ${item.code}`);
            cell(row, `${item.category} / ${item.rarity}`); cell(row, item.start_price);
            cell(row, `${item.fishable ? "가능" : "불가"} / ${item.weight}`);
            const actions = cell(row, "");
            for (const [label, action] of [["수정", () => edit(item)], ["삭제", async () => {
                if (!confirm(`${item.name} 카탈로그를 삭제할까요?`)) return;
                await request(`/admin/item-catalogs/${item.id}`, {method:"DELETE"});
                if (editingId === item.id) resetEditor();
                message("카탈로그를 삭제했습니다.");
                await loadCatalog();
            }]]) {
                const button = document.createElement("button");
                button.type = "button"; button.className = "btn wood"; button.textContent = label;
                button.addEventListener("click", () => run(action, button));
                actions.append(button);
            }
            $("catalog-rows").append(row);
        }
        if (!result.items.length) {
            const row = document.createElement("tr"); cell(row, "등록된 항목이 없습니다.").colSpan = 6; $("catalog-rows").append(row);
        }
        pagination("catalog", result);
    }

    async function loadEvents() {
        const serial = ++eventRequest;
        $("event-rows").replaceChildren();
        $("event-page").textContent = "조회 중...";
        $("event-prev").disabled = $("event-next").disabled = true;
        try {
            const result = await request(`/admin/inventory/${encodeURIComponent(eventItem)}/events?page=${eventPage}&size=20`);
            if (serial !== eventRequest) return;
            for (const item of result.items) {
                const row = document.createElement("tr");
                for (const value of [new Date(item.created_at).toLocaleString(), item.event_type,
                    item.from_owner_id, item.to_owner_id, item.actor_id, `${item.listing_id ?? "—"} / ${item.trade_id ?? "—"}`]) cell(row, value);
                $("event-rows").append(row);
            }
            if (!result.items.length) {
                const row = document.createElement("tr"); cell(row, "기록된 이력이 없습니다.").colSpan = 6; $("event-rows").append(row);
            }
            pagination("event", result);
        } catch (error) {
            if (serial === eventRequest) $("event-page").textContent = "조회 실패";
            throw error;
        }
    }

    async function run(action, button) {
        if (button) button.disabled = true;
        try { await action(); } catch (error) { message(error.message, true); }
        finally { if (button) button.disabled = false; }
    }

    editor.addEventListener("submit", event => {
        event.preventDefault();
        run(async () => {
            const payload = Object.fromEntries(new FormData(editor));
            payload.start_price = Number(payload.start_price); payload.weight = Number(payload.weight);
            payload.fishable = editor.elements.fishable.checked;
            await request("/admin/item-catalogs" + (editingId ? `/${editingId}` : ""), {
                method:editingId ? "PATCH" : "POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload),
            });
            resetEditor(); message("카탈로그를 저장했습니다."); await loadCatalog();
        }, $("save-catalog"));
    });
    $("reset-editor").addEventListener("click", resetEditor);
    $("catalog-filters").addEventListener("submit", event => { event.preventDefault(); catalogPage = 1; run(loadCatalog); });
    $("catalog-prev").addEventListener("click", () => { catalogPage--; run(loadCatalog); });
    $("catalog-next").addEventListener("click", () => { catalogPage++; run(loadCatalog); });
    $("event-search").addEventListener("submit", event => { event.preventDefault(); eventItem = event.target.elements.item_id.value; eventPage = 1; run(loadEvents); });
    $("event-prev").addEventListener("click", () => { eventPage--; run(loadEvents); });
    $("event-next").addEventListener("click", () => { eventPage++; run(loadEvents); });
    run(loadCatalog);
})();

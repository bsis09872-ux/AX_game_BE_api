import { initAdminMembers } from "./admin-members.js";

let viewController;
let navigationController;
const adminPath = /^\/admin(?:\/(?:catalogs(?:\/(?:new|[1-9]\d*\/edit))?|members(?:\/(?:new|[1-9]\d*(?:\/inventory)?))?|history|auctions))?$/;

function isAdminPage(url) {
    return url.origin === location.origin && adminPath.test(url.pathname);
}

function initializeView() {
    viewController = new AbortController();
    const root = document.getElementById("admin-view");
    initAdminItems(root, viewController.signal, navigate);
    initAdminMembers(root, viewController.signal, navigate);
}

async function navigate(path, { fromHistory = false } = {}) {
    const url = new URL(path, location.href);
    if (!isAdminPage(url)) { location.assign(url.href); return; }
    navigationController?.abort();
    const controller = navigationController = new AbortController();
    const current = document.getElementById("admin-view");
    current.setAttribute("aria-busy", "true");
    try {
        const response = await fetch(url, {credentials: "same-origin", cache: "no-store", signal: controller.signal});
        controller.signal.throwIfAborted();
        if (response.redirected || response.status === 401 || response.status === 403) {
            location.assign(response.redirected ? response.url : url.href);
            return;
        }
        const missingAuction = response.status === 404 && url.pathname === '/admin/auctions';
        if (!response.ok && !missingAuction) throw new Error("화면을 불러오지 못했습니다. 다시 눌러 주세요.");
        const html = await response.text();
        controller.signal.throwIfAborted();
        const page = new DOMParser().parseFromString(html, "text/html");
        const next = page.getElementById("admin-view");
        const title = page.getElementById("admin-title");
        if (!next || !title) throw new Error("화면을 불러오지 못했습니다. 다시 눌러 주세요.");

        // 공통 배경과 메뉴 DOM은 유지하고 이전 본문의 조회만 중단한다.
        if (!fromHistory && url.href !== location.href) history.pushState(null, "", url);
        viewController.abort();
        current.replaceWith(next);
        document.title = page.title;
        document.getElementById("admin-title").textContent = title.textContent;
        for (const tab of document.querySelectorAll("[data-admin-tab]")) {
            const updated = page.querySelector(`[data-admin-tab="${tab.dataset.adminTab}"]`);
            tab.href = updated.href;
            tab.textContent = updated.textContent;
            if (updated.hasAttribute("aria-current")) tab.setAttribute("aria-current", "page");
            else tab.removeAttribute("aria-current");
        }
        initializeView();
        next.focus({preventScroll: true});
        window.scrollTo(0, 0);
    } catch (error) {
        if (controller.signal.aborted) return;
        if (fromHistory) { location.replace(url.href); return; }
        const message = current.querySelector("#admin-message");
        message.textContent = error.message;
        message.dataset.error = "true";
    } finally {
        if (navigationController === controller) current.removeAttribute("aria-busy");
    }
}

document.addEventListener("click", event => {
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest("a[href]");
    if (!link || link.hasAttribute("download") || (link.target && link.target !== "_self")) return;
    const url = new URL(link.href);
    if (!isAdminPage(url) || url.hash) return;
    event.preventDefault();
    void navigate(url);
});

document.addEventListener("submit", event => {
    const form = event.target;
    if (event.defaultPrevented || !form.matches('#admin-view form[method="get"]')) return;
    const url = new URL(form.action);
    if (!isAdminPage(url)) return;
    event.preventDefault();
    url.search = new URLSearchParams(new FormData(form)).toString();
    void navigate(url);
});

window.addEventListener("popstate", () => { void navigate(location.href, {fromHistory: true}); });
initializeView();

function initAdminItems(root, signal, navigate) {
    "use strict";
    const $ = id => root.querySelector(`#${id}`);
    const editor = $("catalog-editor");
    let editingId = editor?.dataset.editId || null, catalogPage = 1, eventPage = 1, eventItem = null;
    let catalogRequest = 0, eventRequest = 0;

    function message(text, error = false) {
        $("admin-message").textContent = text;
        $("admin-message").dataset.error = String(error);
    }

    async function request(path, options = {}) {
        const response = await fetch(path, {credentials:"same-origin", cache:"no-store",
            signal: options.method && options.method !== "GET" ? undefined : signal, ...options});
        signal.throwIfAborted();
        if (response.redirected || response.status === 401) {
            location.replace("/login?expired=1");
            throw new Error("다시 로그인해 주세요.");
        }
        if (response.status === 204) return null;
        const data = await response.json();
        signal.throwIfAborted();
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

    const imageNames = {fish_carp:"붕어", fish_mackerel:"고등어", fish_bass:"농어", fish_salmon:"연어", fish_puffer:"복어", fish_golden:"황금 잉어", fish_dragon:"바다용", gem_pearl:"진주", gem_sapphire:"사파이어", gem_black_pearl:"흑진주", misc_boot:"낡은 장화", misc_seaweed:"해초", misc_bottle:"편지병", gift_box:"선물 상자", choco_stick:"초코 스틱", berry_stick:"베리 스틱"};
    function iconUrl(icon) {
        return /^[a-z0-9_]{1,50}$/.test(icon) ? `/static/sprites/item_${icon}.png` : null;
    }
    function setImage(image, icon) {
        const url = iconUrl(icon);
        image.hidden = !url;
        const fallback = image.parentElement.querySelector(".image-fallback");
        if (fallback) fallback.hidden = Boolean(url);
        image.onload = () => { image.hidden = false; if (fallback) fallback.hidden = true; };
        image.onerror = () => { image.hidden = true; if (fallback) fallback.hidden = false; };
        if (url) image.src = url; else image.removeAttribute("src");
    }
    function updatePreview() {
        const f = editor.elements;
        $("preview-name").textContent = f.name.value || "새 아이템";
        $("preview-category").textContent = f.category.value;
        $("preview-rarity").textContent = f.rarity.value;
        $("preview-frame").dataset.rarity = f.rarity.value;
        $("preview-description").textContent = f.description.value || "설명을 입력해 주세요.";
        $("preview-price").textContent = `${Number(f.start_price.value || 0).toLocaleString("ko-KR")} GOLD`;
        $("preview-fishable").textContent = f.fishable.checked ? "가능" : "불가";
        setImage($("preview-image"), f.icon.value);
        for (const button of $("image-gallery").querySelectorAll("button")) {
            button.setAttribute("aria-pressed", String(button.dataset.icon === f.icon.value));
        }
    }
    async function loadImages() {
        const images = await request("/admin/item-images");
        $("image-gallery").replaceChildren();
        for (const item of images) {
            const button = document.createElement("button");
            button.type = "button";
            button.dataset.icon = item.icon;
            const label = imageNames[item.icon] || `업로드 ${item.icon.slice(-6)}`;
            button.title = label; button.setAttribute("aria-label", label);
            const image = document.createElement("img"); image.alt = ""; image.src = item.url;
            const name = document.createElement("span"); name.textContent = label;
            button.append(image, name);
            button.addEventListener("click", () => { editor.elements.icon.value = item.icon; updatePreview(); });
            $("image-gallery").append(button);
        }
        updatePreview();
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
        $("csv-link").href = "/admin/item-catalogs/export.csv?" + params;
        $("catalog-rows").replaceChildren();
        for (const item of result.items) {
            const row = document.createElement("tr");
            const identity = cell(row, "");
            const link = document.createElement("a"); link.className = "admin-item-name"; link.href = `/admin/catalogs/${item.id}/edit`;
            const frame = document.createElement("span"); frame.className = "admin-item-frame small"; frame.dataset.rarity = item.rarity;
            const image = document.createElement("img"); image.alt = "";
            const fallback = document.createElement("span"); fallback.className = "image-fallback"; fallback.textContent = "?"; fallback.hidden = true;
            frame.append(image, fallback); setImage(image, item.icon);
            const name = document.createElement("span"); name.textContent = item.name;
            const code = document.createElement("small"); code.textContent = `#${item.id} / ${item.code}`; name.append(code);
            link.append(frame, name); identity.append(link);
            cell(row, item.category); const rarity = cell(row, item.rarity); rarity.dataset.rarity = item.rarity;
            cell(row, `${Number(item.start_price).toLocaleString("ko-KR")} GOLD`);
            cell(row, `${item.fishable ? "가능" : "불가"} / ${item.weight}`);
            const actions = cell(row, "");
            for (const [label, action] of [["수정", () => navigate(`/admin/catalogs/${item.id}/edit`)], ["삭제", async () => {
                if (!confirm(`${item.name} 카탈로그를 삭제할까요?`)) return;
                await request(`/admin/item-catalogs/${item.id}`, {method:"DELETE"});
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
                for (const value of [new Date(item.created_at).toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC"), item.event_type,
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
        try { await action(); } catch (error) { if (!signal.aborted) message(error.message, true); }
        finally { if (button) button.disabled = false; }
    }

    if (editor) {
        const initial = JSON.parse($("editor-data").textContent);
        if (initial) for (const [key, value] of Object.entries(initial)) {
            const input = editor.elements[key];
            if (input) { if (input.type === "checkbox") input.checked = value; else input.value = value; }
        }
        editor.addEventListener("input", updatePreview);
        updatePreview();
        run(loadImages);
        $("image-upload").addEventListener("change", () => run(async () => {
            const file = $("image-upload").files[0];
            if (!file) return;
            if (file.size > 2 * 1024 * 1024) throw new Error("이미지는 2MB 이하의 파일을 선택해 주세요.");
            $("image-message").textContent = "이미지를 업로드하는 중입니다...";
            $("save-catalog").disabled = true;
            try {
                const result = await request("/admin/item-images", {method:"POST", headers:{"Content-Type":file.type || "application/octet-stream"}, body:file});
                editor.elements.icon.value = result.icon;
                await loadImages();
                $("image-message").textContent = `이미지를 저장했습니다. ${result.width} × ${result.height}px`;
            } catch (error) { $("image-message").textContent = "이미지를 업로드하지 못했습니다."; throw error; }
            finally { $("save-catalog").disabled = false; $("image-upload").value = ""; }
        }, $("image-upload")));
        editor.addEventListener("submit", event => {
            event.preventDefault();
            run(async () => {
                const payload = Object.fromEntries(new FormData(editor));
                payload.start_price = Number(payload.start_price); payload.weight = Number(payload.weight);
                payload.fishable = editor.elements.fishable.checked;
                await request("/admin/item-catalogs" + (editingId ? `/${editingId}` : ""), {
                    method:editingId ? "PATCH" : "POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload),
                });
                await navigate("/admin/catalogs?saved=1");
            }, $("save-catalog"));
        });
    }
    if ($("catalog-filters")) {
        $("catalog-filters").addEventListener("submit", event => { event.preventDefault(); catalogPage = 1; run(loadCatalog); });
        $("catalog-prev").addEventListener("click", () => { catalogPage--; run(loadCatalog); });
        $("catalog-next").addEventListener("click", () => { catalogPage++; run(loadCatalog); });
        if (new URLSearchParams(location.search).has("saved")) message("아이템을 저장했습니다.");
        run(loadCatalog);
    }
    if ($("event-search")) {
        $("event-search").addEventListener("submit", event => { event.preventDefault(); eventItem = event.target.elements.item_id.value; eventPage = 1; run(loadEvents); });
        $("event-prev").addEventListener("click", () => { eventPage--; run(loadEvents); });
        $("event-next").addEventListener("click", () => { eventPage++; run(loadEvents); });
        const itemId = new URLSearchParams(location.search).get('item_id');
        if (itemId && /^[1-9]\d{0,18}$/.test(itemId) && BigInt(itemId) <= 9223372036854775807n) {
            $("event-search").elements.item_id.value = itemId;
            eventItem = itemId;
            run(loadEvents);
        }
    }
    for (const image of root.querySelectorAll('img[data-inventory-icon]')) {
        setImage(image, image.dataset.inventoryIcon);
    }
}

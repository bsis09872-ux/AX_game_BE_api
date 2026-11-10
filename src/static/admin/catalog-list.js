import { setImage } from "./item-images.js";

// 목록의 필터, 페이지 이동과 삭제 후 재조회를 담당한다.
export function initCatalogList(context) {
    const { getElement, request, message, appendCell, updatePagination, run, navigate } = context;
    if (!getElement("catalog-filters")) {
        return;
    }

    let catalogPage = 1;
    let catalogRequest = 0;

    async function loadCatalog() {
        const requestId = ++catalogRequest;
        const params = new URLSearchParams(new FormData(getElement("catalog-filters")));
        for (const key of ["category", "rarity"]) if (!params.get(key)) params.delete(key);
        params.set("page", catalogPage);
        params.set("size", 20);

        const result = await request("/admin/item-catalogs?" + params);
        if (requestId !== catalogRequest) return;
        if (!result.items.length && catalogPage > 1) {
            catalogPage--;
            return loadCatalog();
        }
        getElement("csv-link").href = "/admin/item-catalogs/export.csv?" + params;

        getElement("catalog-rows").replaceChildren();
        for (const item of result.items) {
            const row = document.createElement("tr");

            const identity = appendCell(row, "");

            const link = document.createElement("a");
            link.className = "admin-item-name";
            link.href = `/admin/catalogs/${item.id}/edit`;

            const frame = document.createElement("span");
            frame.className = "admin-item-frame small";
            frame.dataset.rarity = item.rarity;

            const image = document.createElement("img");
            image.alt = "";

            const fallback = document.createElement("span");
            fallback.className = "image-fallback";
            fallback.textContent = "?";
            fallback.hidden = true;
            frame.append(image, fallback);
            setImage(image, item.icon);

            const name = document.createElement("span");
            name.textContent = item.name;

            const code = document.createElement("small");
            code.textContent = `#${item.id} / ${item.code}`;
            name.append(code);
            link.append(frame, name);
            identity.append(link);
            appendCell(row, item.category);

            const rarity = appendCell(row, item.rarity);
            rarity.dataset.rarity = item.rarity;
            appendCell(row, `${Number(item.start_price).toLocaleString("ko-KR")} GOLD`);
            appendCell(row, `${item.fishable ? "가능" : "불가"} / ${item.weight}`);

            const actions = appendCell(row, "");
            for (const [label, action] of [
                ["수정", () => navigate(`/admin/catalogs/${item.id}/edit`)],
                [
                    "삭제",
                    async () => {
                        if (!confirm(`${item.name} 카탈로그를 삭제할까요?`)) return;
                        await request(`/admin/item-catalogs/${item.id}`, { method: "DELETE" });
                        message("카탈로그를 삭제했습니다.");
                        await loadCatalog();
                    },
                ],
            ]) {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "btn wood";
                button.textContent = label;
                button.addEventListener("click", () => run(action, button));
                actions.append(button);
            }
            getElement("catalog-rows").append(row);
        }
        if (!result.items.length) {
            const row = document.createElement("tr");
            appendCell(row, "등록된 항목이 없습니다.").colSpan = 6;
            getElement("catalog-rows").append(row);
        }

        updatePagination("catalog", result);
    }

    // 입력 이벤트는 이 화면의 요소에만 연결한다.
    getElement("catalog-filters").addEventListener("submit", (event) => {
        event.preventDefault();
        catalogPage = 1;
        run(loadCatalog);
    });

    getElement("catalog-prev").addEventListener("click", () => {
        catalogPage--;
        run(loadCatalog);
    });

    getElement("catalog-next").addEventListener("click", () => {
        catalogPage++;
        run(loadCatalog);
    });
    if (new URLSearchParams(location.search).has("saved")) message("아이템을 저장했습니다.");
    run(loadCatalog);
}

// 공통 배경과 헤더 노드는 유지하고 서버가 돌려준 화면 정보를 반영한다.
export function renderPage(nextPage) {
    const currentMain = document.getElementById("main-content");
    const nextMain = nextPage.getElementById("main-content");
    const currentAdmin = currentMain.querySelector("#admin-view");
    const nextAdmin = nextMain.querySelector("#admin-view");

    if (currentAdmin && nextAdmin) {
        currentAdmin.replaceWith(nextAdmin);
        document.getElementById("admin-title").textContent =
            nextPage.getElementById("admin-title").textContent;

        for (const tab of document.querySelectorAll("[data-admin-tab]")) {
            const nextTab = nextPage.querySelector(`[data-admin-tab="${tab.dataset.adminTab}"]`);
            tab.href = nextTab.href;
            tab.textContent = nextTab.textContent;
            tab.toggleAttribute("aria-current", nextTab.hasAttribute("aria-current"));

            if (nextTab.hasAttribute("aria-current")) {
                tab.setAttribute("aria-current", "page");
            }
        }
    } else {
        currentMain.replaceChildren(...nextMain.childNodes);
    }

    // 로그인 상태와 선택 메뉴가 달라진 부분만 갱신한다.
    for (const slot of document.querySelectorAll("[data-shell-slot]")) {
        const nextSlot = nextPage.querySelector(`[data-shell-slot="${slot.dataset.shellSlot}"]`);

        if (nextSlot && slot.innerHTML !== nextSlot.innerHTML) {
            slot.replaceChildren(...nextSlot.childNodes);
        }
    }

    for (const attribute of [...document.body.attributes]) {
        document.body.removeAttribute(attribute.name);
    }

    for (const attribute of nextPage.body.attributes) {
        document.body.setAttribute(attribute.name, attribute.value);
    }

    document.title = nextPage.title;
    return currentAdmin && nextAdmin ? nextAdmin : currentMain;
}

// 새 CSS 로드가 끝날 때까지 이전 화면의 스타일을 유지한다.
export async function preparePageStyles(nextPage, signal) {
    const currentLinks = [
        ...document.querySelectorAll("link[data-page-style]:not([data-page-style-pending])"),
    ];
    const nextLinks = [...nextPage.querySelectorAll("link[data-page-style]")];
    const nextUrls = new Set(nextLinks.map((link) => link.href));
    const addedLinks = [];

    try {
        await Promise.all(
            nextLinks.map(async (nextLink) => {
                if (currentLinks.some((link) => link.href === nextLink.href)) {
                    return;
                }

                const link = document.createElement("link");
                link.rel = "stylesheet";
                link.href = nextLink.href;
                link.dataset.pageStyle = "";
                link.dataset.pageStylePending = "";
                link.media = "not all";
                addedLinks.push(link);

                await new Promise((resolve, reject) => {
                    const timeout = setTimeout(
                        () => finish(new Error("화면 스타일을 불러오지 못했습니다.")),
                        10000,
                    );

                    function finish(error) {
                        clearTimeout(timeout);
                        signal.removeEventListener("abort", onAbort);
                        link.onload = null;
                        link.onerror = null;
                        error ? reject(error) : resolve();
                    }

                    function onAbort() {
                        finish(signal.reason);
                    }

                    link.onload = () => finish();
                    link.onerror = () => finish(new Error("화면 스타일을 불러오지 못했습니다."));
                    signal.addEventListener("abort", onAbort, { once: true });
                    document.head.append(link);
                });
            }),
        );

        signal.throwIfAborted();
    } catch (error) {
        addedLinks.forEach((link) => link.remove());
        throw error;
    }

    return {
        activate() {
            addedLinks.forEach((link) => link.removeAttribute("media"));
        },
        finish() {
            addedLinks.forEach((link) => link.removeAttribute("data-page-style-pending"));
            currentLinks
                .filter((link) => !nextUrls.has(link.href))
                .forEach((link) => link.remove());
        },
        cancel() {
            addedLinks.forEach((link) => link.remove());
        },
    };
}

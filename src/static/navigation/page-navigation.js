import { preparePageStyles, renderPage } from "./page-renderer.js";

export function createPageNavigation(initializePage) {
    let requestController;
    let pageController;
    let submitting = false;

    const message = document.getElementById("navigation-message");

    function mountPage() {
        pageController = new AbortController();
        initializePage({
            root: document.getElementById("main-content"),
            signal: pageController.signal,
            navigate,
        });
    }

    function showError(text) {
        message.textContent = text;
        message.hidden = false;
    }

    async function navigate(path, options = {}) {
        if (submitting) {
            return;
        }

        const url = new URL(path, location.href);
        const method = options.method || "GET";
        const isSubmission = method !== "GET";

        if (url.origin !== location.origin) {
            location.assign(url.href);
            return;
        }

        requestController?.abort();
        const controller = new AbortController();
        requestController = controller;
        submitting = isSubmission;

        const main = document.getElementById("main-content");
        main.setAttribute("aria-busy", "true");
        message.hidden = true;

        try {
            const response = await fetch(url, {
                method,
                body: options.body,
                credentials: "same-origin",
                cache: "no-store",
                signal: controller.signal,
            });
            controller.signal.throwIfAborted();

            if (new URL(response.url).origin !== location.origin) {
                throw new Error("다른 사이트의 화면은 현재 페이지에 표시할 수 없습니다.");
            }

            if (response.status >= 500) {
                throw new Error("화면을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.");
            }

            const contentType = response.headers.get("content-type") || "";
            const html = contentType.includes("text/html") ? await response.text() : "";
            const nextPage = new DOMParser().parseFromString(html, "text/html");
            const nextMain = nextPage.getElementById("main-content");

            // 공통 레이아웃을 사용하지 않는 GET 주소는 브라우저의 일반 이동으로 처리한다.
            // POST는 성공 여부를 알 수 없더라도 자동으로 재전송하지 않는다.
            if (!nextMain || nextPage.body.dataset.pageNavigation !== "true") {
                if (isSubmission) {
                    throw new Error(
                        "처리 결과를 표시하지 못했습니다. 결과를 확인한 뒤 다시 시도해 주세요.",
                    );
                }

                location.assign(response.url);
                return;
            }

            const applyStyles = await preparePageStyles(nextPage, controller.signal);
            controller.signal.throwIfAborted();

            const nextUrl = new URL(response.url);
            if (!response.redirected) {
                nextUrl.hash = url.hash;
            }

            if (options.fromHistory || options.replace) {
                history.replaceState(null, "", nextUrl);
            } else if (nextUrl.href !== location.href) {
                history.pushState(null, "", nextUrl);
            }

            // 이전 화면의 이벤트와 타이머를 정리한 뒤 새 화면을 연결한다.
            pageController.abort();
            const focusTarget = renderPage(nextPage);
            applyStyles();
            submitting = false;
            mountPage();
            focusTarget.focus({ preventScroll: true });

            const anchor =
                nextUrl.hash && document.getElementById(decodeURIComponent(nextUrl.hash.slice(1)));
            if (anchor) {
                anchor.scrollIntoView();
            } else {
                window.scrollTo(0, 0);
            }
        } catch (error) {
            if (controller.signal.aborted) {
                return;
            }

            if (options.fromHistory && !isSubmission) {
                location.replace(url.href);
                return;
            }

            const text = isSubmission
                ? "요청 결과를 확인하지 못했습니다. 중복 제출 전에 처리 결과를 확인해 주세요."
                : error.message;
            showError(text);
        } finally {
            if (requestController === controller) {
                submitting = false;
                main.removeAttribute("aria-busy");
            }
        }
    }

    function onLinkClick(event) {
        if (
            event.defaultPrevented ||
            event.button !== 0 ||
            event.ctrlKey ||
            event.metaKey ||
            event.shiftKey ||
            event.altKey
        ) {
            return;
        }

        const link = event.target.closest("a[href]");
        if (
            !link ||
            link.closest("[data-full-reload]") ||
            link.hasAttribute("download") ||
            (link.target && link.target !== "_self")
        ) {
            return;
        }

        const url = new URL(link.href);
        const samePageAnchor =
            url.hash && url.pathname === location.pathname && url.search === location.search;
        if (
            url.origin !== location.origin ||
            !["http:", "https:"].includes(url.protocol) ||
            samePageAnchor ||
            url.pathname.startsWith("/static/")
        ) {
            return;
        }

        event.preventDefault();
        void navigate(url);
    }

    async function onFormSubmit(event) {
        const form = event.target;
        const submitter = event.submitter;
        const method = (submitter?.getAttribute("formmethod") || form.method).toUpperCase();
        const target = submitter?.getAttribute("formtarget") || form.target;

        if (
            event.defaultPrevented ||
            form.closest("[data-full-reload]") ||
            (target && target !== "_self")
        ) {
            return;
        }
        if (method !== "GET" && !(method === "POST" && form.hasAttribute("data-page-form"))) {
            return;
        }

        const url = new URL(submitter?.getAttribute("formaction") || form.action, location.href);
        if (url.origin !== location.origin) {
            return;
        }

        event.preventDefault();
        if (submitting) {
            return;
        }

        const values = new FormData(form, submitter);
        if (method === "GET") {
            url.search = new URLSearchParams(values).toString();
            await navigate(url);
            return;
        }

        if (submitter) {
            submitter.disabled = true;
        }

        try {
            await navigate(url, { method, body: values });
        } finally {
            if (submitter) {
                submitter.disabled = false;
            }
        }
    }

    function start() {
        document.addEventListener("click", onLinkClick);
        document.addEventListener("submit", onFormSubmit);
        window.addEventListener("popstate", () => {
            if (submitting) {
                location.reload();
                return;
            }
            void navigate(location.href, { fromHistory: true });
        });
        mountPage();
    }

    return { start, navigate };
}

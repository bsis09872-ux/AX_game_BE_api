// 관리자 화면에서 공통으로 사용하는 요청, 상태 안내와 표 출력을 묶는다.
export function createAdminContext({ root, signal, navigate }) {
    const getElement = (id) => root.querySelector(`#${id}`);

    function message(text, error = false) {
        getElement("admin-message").textContent = text;
        getElement("admin-message").dataset.error = String(error);
    }

    async function request(path, options = {}) {
        // 조회는 화면 종료와 함께 취소한다. 저장 요청은 서버 처리 결과를 기다린다.
        const response = await fetch(path, {
            credentials: "same-origin",
            cache: "no-store",
            signal: options.method && options.method !== "GET" ? undefined : signal,
            ...options,
        });
        signal.throwIfAborted();

        if (response.redirected || response.status === 401) {
            void navigate("/login?expired=1", { replace: true });
            throw new Error("다시 로그인해 주세요.");
        }
        if (response.status === 204) {
            return null;
        }

        const data = await response.json();
        signal.throwIfAborted();

        if (!response.ok) {
            const detail = data.detail;
            throw new Error(
                Array.isArray(detail)
                    ? "입력 형식과 값을 확인해 주세요."
                    : detail?.message ||
                          (typeof detail === "string" ? detail : "요청을 처리하지 못했습니다."),
            );
        }

        return data;
    }

    function appendCell(row, text) {
        const node = document.createElement("td");
        node.textContent = text ?? "—";
        row.append(node);

        return node;
    }

    function updatePagination(prefix, result) {
        getElement(prefix + "-page").textContent =
            `${result.page} / ${Math.max(1, Math.ceil(result.total / result.size))} 페이지, ${result.total}건`;
        getElement(prefix + "-prev").disabled = result.page <= 1;
        getElement(prefix + "-next").disabled = result.page * result.size >= result.total;
    }

    async function run(action, button) {
        if (button) {
            button.disabled = true;
        }

        try {
            await action();
        } catch (error) {
            if (!signal.aborted) message(error.message, true);
        } finally {
            if (button) {
                button.disabled = false;
            }
        }
    }

    return { getElement, request, message, appendCell, updatePagination, run, signal, navigate };
}

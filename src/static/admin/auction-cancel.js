// 관리자 웹 인증을 사용하는 요청만 보내고, 실제 취소 처리는 서버에 맡긴다.
export function initAuctionCancel({ getElement, request, message, signal, navigate }) {
    const form = getElement("auction-cancel-form");
    if (!form) return;

    const button = form.querySelector("button[type='submit']");
    let submitting = false;
    let completed = false;
    button.disabled = false;

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (submitting || completed) return;

        if (!window.confirm(`매물 #${form.dataset.listingId}을 강제 취소하시겠습니까?\n취소 후 되돌릴 수 없습니다.`)) {
            return;
        }

        submitting = true;
        button.disabled = true;
        message("취소 처리 중입니다.");

        try {
            await request(form.action, {
                method: "POST",
            });
            completed = true;
            message("매물을 취소했습니다. 최신 상태를 조회합니다.");
            await navigate(location.href, { replace: true });
        } catch (error) {
            if (!signal.aborted) {
                message(error instanceof TypeError
                    ? "응답을 받지 못했습니다. 매물을 다시 조회해 처리 결과를 확인해 주세요."
                    : error.message, true);
            }
        } finally {
            submitting = false;
            button.disabled = completed;
        }
    }, { signal });
}

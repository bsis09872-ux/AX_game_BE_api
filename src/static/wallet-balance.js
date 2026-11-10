// 헤더에 사용 가능 금액을 표시한다 (지갑 담당).
// 로그인 쿠키는 HttpOnly라 /v1 API 대신 쿠키 인증 경로 GET /wallet/balance를 부른다.
// 페이지를 옮길 때마다 다시 조회해서 입찰·낙찰로 바뀐 금액을 반영한다.

let lastText = null; // 화면 전환 중 헤더가 잠깐 비지 않도록 직전 값을 먼저 보여 준다

export function initWalletBalance({ signal }) {
    const target = document.querySelector("[data-wallet-balance]");
    if (!target) {
        return;
    }

    // 로그인 화면에서는 부르지 않는다 (auth-session.js와 같은 기준)
    const page = document.body.dataset.authPage;
    const loggedInPage =
        page === "me" || page === "admin" || document.body.dataset.sessionProtected === "true";
    if (!loggedInPage) {
        lastText = null;
        target.hidden = true;
        return;
    }

    if (lastText) {
        show(target, lastText);
    }

    void refresh(target, signal);
}

async function refresh(target, signal) {
    try {
        const response = await fetch("/wallet/balance", {
            credentials: "same-origin",
            cache: "no-store",
            redirect: "manual", // 로그인 만료면 /login으로 리다이렉트된다. 따라가지 않고 표시만 숨긴다
            signal,
        });
        if (!response.ok) {
            target.hidden = true;
            return;
        }
        const { available_balance: amount } = await response.json();
        lastText = `${amount.toLocaleString("ko-KR")} GOLD`;
        show(target, lastText);
    } catch (error) {
        // 다른 화면으로 넘어가며 취소된 요청이거나 통신 오류다. 헤더 표시만 실패하므로 조용히 넘어간다.
        if (error.name !== "AbortError") {
            target.hidden = true;
        }
    }
}

function show(target, text) {
    target.textContent = text;
    target.hidden = false;
}

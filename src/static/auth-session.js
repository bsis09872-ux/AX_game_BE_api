// 로그인 복구와 내 정보 화면의 자동 갱신을 담당한다.
// 토큰 원문은 JavaScript에서 읽지 않고 브라우저가 HttpOnly 쿠키로 전달한다.
(() => {
    "use strict";

    const page = document.body.dataset.authPage;

    // 일반 로그인 화면에서는 실행하지 않는다. 복구할 쿠키가 있거나 /me일 때만 확인한다.
    if (page !== "me" && document.body.dataset.resume !== "true") {
        return;
    }

    let pending = null; // 같은 탭에서 진행 중인 인증 확인 요청
    let timer = null; // 다음 인증 확인을 예약한 타이머

    // 현재 access token을 서버에서 검증하고 남은 유효 시간을 조회한다.
    async function status() {
        const response = await fetch("/session", {
            credentials: "same-origin",
            cache: "no-store",
        });

        // 인증 만료와 서버/통신 장애를 구분한다. 장애는 호출부에서 재시도한다.
        if (response.status === 401) {
            return null;
        }

        if (!response.ok) {
            throw new Error("session unavailable");
        }

        return response.json();
    }

    // access token의 남은 시간이 30초 이하이면 refresh cookie로 새 토큰을 요청한다.
    async function renewIfNeeded() {
        // 탭 간 잠금을 얻은 뒤 다시 조회해야 다른 탭이 갱신한 쿠키도 반영된다.
        const current = await status();

        if (current && current.expires_in > 30) {
            return current;
        }

        const response = await fetch("/session/refresh", {
            method: "POST",
            credentials: "same-origin",
            cache: "no-store",
        });

        if (response.status === 401) {
            return null;
        }

        if (!response.ok) {
            throw new Error("refresh unavailable");
        }

        return response.json();
    }

    // 인증 확인 결과에 따라 화면을 이동하거나 다음 확인을 예약한다.
    async function update() {
        // 초기 로드, 화면 복귀, 타이머가 겹쳐도 같은 탭에서는 한 요청만 진행한다.
        if (pending) {
            return pending;
        }

        pending = (async () => {
            try {
                // Web Locks 지원 브라우저는 여러 탭의 갱신도 순서대로 처리한다.
                // 미지원 브라우저에서는 위 pending으로 탭 내부 중복만 막는다.
                const result = navigator.locks
                    ? await navigator.locks.request("ax-game-session-refresh", renewIfNeeded)
                    : await renewIfNeeded();

                clearTimeout(timer);

                // 세션 만료/폐기로 갱신할 수 없으면 재로그인이 필요하다.
                if (!result) {
                    if (page === "me") {
                        location.replace("/login");
                    } else {
                        document.getElementById("session-message").textContent = "다시 로그인해 주세요.";
                    }

                    return;
                }

                // 로그인 화면에서 기존 쿠키로 인증을 복구했다면 내 정보 화면으로 이동한다.
                if (page === "login") {
                    location.replace("/me");
                    return;
                }

                const message = document.getElementById("session-message");

                if (message) {
                    message.textContent = "";
                }

                // access 만료 30초 전에 다시 확인한다. 로그인 세션의 최종 만료는 연장하지 않는다.
                timer = setTimeout(update, Math.max(1000, (result.expires_in - 30) * 1000));
            } catch {
                // 통신 실패는 로그아웃으로 취급하지 않고 30초 뒤 다시 확인한다.
                clearTimeout(timer);
                timer = setTimeout(update, 30000);

                const message = document.getElementById("session-message");

                if (message) {
                    message.textContent = "연결을 확인하고 있습니다.";
                }
            } finally {
                // 성공/실패와 관계없이 다음 확인 요청을 받을 수 있게 해제한다.
                pending = null;
            }
        })();

        return pending;
    }

    // 다른 탭에서 돌아오면 백그라운드에서 지연됐을 수 있는 인증 상태를 확인한다.
    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") {
            update();
        }
    });

    // 뒤로 가기 등으로 페이지가 복원될 때도 확인하고, 최초 로드 시에도 한 번 실행한다.
    window.addEventListener("pageshow", update);
    update();
})();

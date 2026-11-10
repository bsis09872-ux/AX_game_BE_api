// 웹소켓 재연결도 공통 인증 갱신 잠금을 사용한다.
export async function ensureSession(signal) {
    async function renew() {
        signal.throwIfAborted();
        const requestSignal = AbortSignal.any([signal, AbortSignal.timeout(8000)]);
        const current = await fetch("/session", {
            credentials: "same-origin",
            cache: "no-store",
            signal: requestSignal,
        });
        if (!current.ok && current.status !== 401) throw new Error("session unavailable");
        const status = current.ok ? await current.json() : null;
        if (status && status.expires_in > 30) return status;

        signal.throwIfAborted();
        const response = await fetch("/session/refresh", {
            method: "POST",
            credentials: "same-origin",
            cache: "no-store",
            signal: requestSignal,
        });
        if (response.status === 401) return null;
        if (!response.ok) throw new Error("refresh unavailable");
        return response.json();
    }

    return navigator.locks
        ? navigator.locks.request("ax-game-session-refresh", { signal }, renew)
        : renew();
}

// 로그인 복구와 내 정보 화면의 자동 갱신을 담당한다.
// 토큰 원문은 JavaScript에서 읽지 않고 브라우저가 HttpOnly 쿠키로 전달한다.
export function initAuthSession({ signal, navigate }) {
    const page = document.body.dataset.authPage;
    const protectedPage =
        page === "me" || page === "admin" || document.body.dataset.sessionProtected === "true";

    // 일반 로그인 화면에서는 실행하지 않는다. 복구할 쿠키가 있거나 /me일 때만 확인한다.
    if (!protectedPage && document.body.dataset.resume !== "true") {
        return;
    }

    let pending = null; // 같은 탭에서 진행 중인 인증 확인 요청
    let timer = null; // 다음 인증 확인을 예약한 타이머
    let expiryTimer = null; // 서버가 알려 준 로그인 세션의 최종 만료 타이머
    let sessionDeadline = Infinity;
    let ended = false;

    function requireLogin() {
        ended = true;
        clearTimeout(timer);
        clearTimeout(expiryTimer);

        if (protectedPage) {
            void navigate("/login?expired=1", { replace: true });
        } else {
            const message = document.getElementById("session-message");
            if (message) {
                message.textContent = "다시 로그인해 주세요.";
            }
        }
    }

    function checkExpiry() {
        clearTimeout(expiryTimer);

        const remaining = sessionDeadline - performance.now();
        if (remaining <= 0) {
            requireLogin();
            return;
        }

        // 최대 30일 세션도 setTimeout의 약 24.8일 상한을 넘지 않게 나눠 예약한다.
        expiryTimer = setTimeout(checkExpiry, Math.min(remaining, 2147483647));
    }

    function scheduleExpiry(seconds) {
        // 서버의 남은 수명으로 예약한다. 화면 조작이나 통신 실패로 세션을 연장하지 않는다.
        sessionDeadline = performance.now() + seconds * 1000;
        checkExpiry();
    }

    // 인증 확인 결과에 따라 화면을 이동하거나 다음 확인을 예약한다.
    async function update() {
        // 백그라운드 타이머가 지연돼도 화면에 돌아오면 만료부터 확인한다.
        if (ended) {
            return;
        }
        if (performance.now() >= sessionDeadline) {
            requireLogin();
            return;
        }

        // 초기 로드, 화면 복귀, 타이머가 겹쳐도 같은 탭에서는 한 요청만 진행한다.
        if (pending) {
            return pending;
        }

        pending = (async () => {
            try {
                // Web Locks 지원 브라우저는 여러 탭의 갱신도 순서대로 처리한다.
                // 미지원 브라우저에서는 위 pending으로 탭 내부 중복만 막는다.
                const result = await ensureSession(signal);

                // 요청을 기다리는 중 세션 만료 타이머가 실행됐다면 결과를 적용하지 않는다.
                if (ended) {
                    return;
                }

                clearTimeout(timer);

                // 세션 만료/폐기로 갱신할 수 없으면 재로그인이 필요하다.
                if (!result) {
                    requireLogin();
                    return;
                }

                scheduleExpiry(result.session_expires_in);
                if (ended) {
                    return;
                }

                // 로그인 화면에서 기존 쿠키로 인증을 복구했다면 내 정보 화면으로 이동한다.
                if (page === "login") {
                    void navigate("/me", { replace: true });
                    return;
                }

                const message = document.getElementById("session-message");

                if (message) {
                    message.textContent = "";
                }

                // access 만료 30초 전에 다시 확인한다. 로그인 세션의 최종 만료는 연장하지 않는다.
                timer = setTimeout(update, Math.max(1000, (result.expires_in - 30) * 1000));
            } catch {
                if (ended) {
                    return;
                }
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

    // 화면을 떠나면 이전 화면의 타이머와 이벤트를 함께 해제한다.
    signal.addEventListener(
        "abort",
        () => {
            ended = true;
            clearTimeout(timer);
            clearTimeout(expiryTimer);
        },
        { once: true },
    );

    // 다른 탭에서 돌아오면 백그라운드에서 지연됐을 수 있는 인증 상태를 확인한다.
    document.addEventListener(
        "visibilitychange",
        () => {
            if (document.visibilityState === "visible") {
                update();
            }
        },
        { signal },
    );

    // 뒤로 가기 등으로 페이지가 복원될 때도 확인하고, 최초 로드 시에도 한 번 실행한다.
    window.addEventListener("pageshow", update, { signal });
    update();
}

(() => {
  "use strict";
  const page = document.body.dataset.authPage;
  if (page !== "me" && document.body.dataset.resume !== "true") return;
  let pending = null;
  let timer = null;

  async function status() {
    const response = await fetch("/session", { credentials: "same-origin", cache: "no-store" });
    if (response.status === 401) return null;
    if (!response.ok) throw new Error("session unavailable");
    return response.json();
  }

  async function renewIfNeeded() {
    // 탭 간 잠금을 얻은 뒤 쿠키 상태를 다시 확인한다.
    const current = await status();
    if (current && current.expires_in > 30) return current;
    const response = await fetch("/session/refresh", {
      method: "POST", credentials: "same-origin", cache: "no-store",
    });
    if (response.status === 401) return null;
    if (!response.ok) throw new Error("refresh unavailable");
    return response.json();
  }

  async function update() {
    if (pending) return pending;
    pending = (async () => {
      try {
        const result = navigator.locks
          ? await navigator.locks.request("ax-game-session-refresh", renewIfNeeded)
          : await renewIfNeeded();
        clearTimeout(timer);
        if (!result) {
          if (page === "me") location.replace("/login");
          else document.getElementById("session-message").textContent = "다시 로그인해 주세요.";
          return;
        }
        if (page === "login") {
          location.replace("/me");
          return;
        }
        const message = document.getElementById("session-message");
        if (message) message.textContent = "";
        timer = setTimeout(update, Math.max(1000, (result.expires_in - 30) * 1000));
      } catch {
        // 통신 실패를 로그아웃으로 취급하지 않고 잠시 뒤 다시 확인한다.
        clearTimeout(timer);
        timer = setTimeout(update, 30000);
        const message = document.getElementById("session-message");
        if (message) message.textContent = "연결을 확인하고 있습니다.";
      } finally {
        pending = null;
      }
    })();
    return pending;
  }

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") update();
  });
  window.addEventListener("pageshow", update);
  update();
})();

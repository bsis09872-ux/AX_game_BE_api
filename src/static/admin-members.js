export function initAdminMembers(root, signal, navigate) {
    "use strict";
    const $ = id => root.querySelector(`#${id}`);
    const message = $("admin-message");
    async function submit(form, path, method, body) {
        const button = form.querySelector('button[type="submit"], button:not([type])');
        button.disabled = true;
        message.textContent = "저장 중입니다...";
        message.dataset.error = "false";
        try {
            const response = await fetch(path, {method, credentials:"same-origin", cache:"no-store",
                headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
            signal.throwIfAborted();
            if (response.redirected || response.status === 401) { location.replace("/login?expired=1"); return; }
            const data = await response.json();
            signal.throwIfAborted();
            if (!response.ok) {
                const detail = data.detail;
                throw new Error(Array.isArray(detail) ? "입력 형식과 값을 확인해 주세요." : detail?.message || detail || "저장하지 못했습니다.");
            }
            form.reset();
            await navigate(`/admin/members/${data.id}?saved=1`);
        } catch (error) { if (!signal.aborted) { message.textContent = error.message; message.dataset.error = "true"; } }
        finally { button.disabled = false; }
    }
    const create = $("member-create");
    const bid = $("member-bid");
    if (bid) {
        $("bid-timezone").textContent = `(${Intl.DateTimeFormat().resolvedOptions().timeZone})`;
        if (bid.dataset.until) {
            const date = new Date(bid.dataset.until);
            const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
            bid.elements.until.value = local.toISOString().slice(0,16);
        }
        bid.addEventListener("submit", event => {
            event.preventDefault();
            const date = new Date(bid.elements.until.value);
            if (!Number.isFinite(date.getTime()) || date <= new Date()) {
                message.textContent = "미래의 종료 시각을 선택해 주세요."; message.dataset.error = "true"; return;
            }
            submit(bid, `/admin/member-accounts/${bid.dataset.memberId}/bid-restriction`, "PATCH", {until:date.toISOString()});
        });
        $("clear-bid").addEventListener("click", () => {
            if (!confirm("관리자가 설정한 입찰 제한을 해제할까요? 경매 자동 제한은 유지됩니다.")) return;
            submit(bid, `/admin/member-accounts/${bid.dataset.memberId}/bid-restriction`, "PATCH", {until:null});
        });
    }
    const login = $("member-login");
    login?.addEventListener("submit", event => {
        event.preventDefault();
        const suspended = login.dataset.suspend === "true";
        if (!confirm(suspended ? "이 회원의 로그인을 정지하고 기존 세션을 종료할까요?" : "로그인 정지를 해제할까요?")) return;
        submit(login, `/admin/member-accounts/${login.dataset.memberId}/login-suspension`, "PATCH", {suspended});
    });
    const role = $("member-role");
    role?.addEventListener("submit", event => {
        event.preventDefault();
        if (!confirm(`이 회원의 권한을 ${role.elements.role.value}로 변경할까요?`)) return;
        submit(role, `/admin/member-accounts/${role.dataset.memberId}/role`, "PATCH", {role:role.elements.role.value});
    });
    create?.addEventListener("submit", event => {
        event.preventDefault();
        const body = Object.fromEntries(new FormData(create));
        if (body.password !== body.password_confirm) {
            message.textContent = "비밀번호 확인이 일치하지 않습니다."; message.dataset.error = "true"; return;
        }
        delete body.password_confirm;
        submit(create, "/admin/member-accounts", "POST", body);
    });
    if (location.pathname.startsWith("/admin/members/") && new URLSearchParams(location.search).has("saved")) message.textContent = "회원 정보를 저장했습니다.";
}

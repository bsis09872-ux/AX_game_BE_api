(() => {
    "use strict";
    const message = document.getElementById("admin-message");
    async function submit(form, path, method, body) {
        const button = form.querySelector('button[type="submit"], button:not([type])');
        button.disabled = true;
        message.textContent = "저장 중입니다...";
        message.dataset.error = "false";
        try {
            const response = await fetch(path, {method, credentials:"same-origin", cache:"no-store",
                headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
            if (response.redirected || response.status === 401) { location.replace("/login?expired=1"); return; }
            const data = await response.json();
            if (!response.ok) {
                const detail = data.detail;
                throw new Error(Array.isArray(detail) ? "입력 형식과 값을 확인해 주세요." : detail?.message || detail || "저장하지 못했습니다.");
            }
            form.reset();
            location.href = `/admin/members/${data.id}?saved=1`;
        } catch (error) { message.textContent = error.message; message.dataset.error = "true"; }
        finally { button.disabled = false; }
    }
    const create = document.getElementById("member-create");
    const role = document.getElementById("member-role");
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
    if (new URLSearchParams(location.search).has("saved")) message.textContent = "회원 정보를 저장했습니다.";
})();

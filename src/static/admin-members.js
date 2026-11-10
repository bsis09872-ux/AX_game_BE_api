// 회원 등록과 권한 변경 이벤트를 연결한다. 화면 이동은 공통 navigate에 맡긴다.
export function initAdminMembers(root, signal, navigate) {
    const getElement = (id) => root.querySelector(`#${id}`);
    const message = getElement("admin-message");

    async function submit(form, path, method, body) {
        const button = form.querySelector('button[type="submit"], button:not([type])');
        button.disabled = true;
        message.textContent = "저장 중입니다...";
        message.dataset.error = "false";

        try {
            const response = await fetch(path, {
                method,
                credentials: "same-origin",
                cache: "no-store",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            signal.throwIfAborted();

            if (response.redirected || response.status === 401) {
                void navigate("/login?expired=1", { replace: true });
                return;
            }

            const data = await response.json();
            signal.throwIfAborted();

            if (!response.ok) {
                const detail = data.detail;
                throw new Error(
                    Array.isArray(detail)
                        ? "입력 형식과 값을 확인해 주세요."
                        : detail?.message || detail || "저장하지 못했습니다.",
                );
            }

            form.reset();
            await navigate(`/admin/members/${data.id}?saved=1`);
        } catch (error) {
            if (!signal.aborted) {
                message.textContent = error.message;
                message.dataset.error = "true";
            }
        } finally {
            button.disabled = false;
        }
    }

    // 각 폼은 해당 화면에 있을 때만 연결한다.
    const createForm = getElement("member-create");
    const bidForm = getElement("member-bid");
    if (bidForm) {
        getElement("bid-timezone").textContent =
            `(${Intl.DateTimeFormat().resolvedOptions().timeZone})`;
        if (bidForm.dataset.until) {
            const date = new Date(bidForm.dataset.until);
            const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
            bidForm.elements.until.value = local.toISOString().slice(0, 16);
        }
        bidForm.addEventListener("submit", (event) => {
            event.preventDefault();
            const date = new Date(bidForm.elements.until.value);
            if (!Number.isFinite(date.getTime()) || date <= new Date()) {
                message.textContent = "미래의 종료 시각을 선택해 주세요.";
                message.dataset.error = "true";
                return;
            }
            submit(
                bidForm,
                `/admin/member-accounts/${bidForm.dataset.memberId}/bid-restriction`,
                "PATCH",
                {
                    until: date.toISOString(),
                },
            );
        });
        getElement("clear-bid").addEventListener("click", () => {
            if (!confirm("관리자가 설정한 입찰 제한을 해제할까요? 경매 자동 제한은 유지됩니다."))
                return;
            submit(
                bidForm,
                `/admin/member-accounts/${bidForm.dataset.memberId}/bid-restriction`,
                "PATCH",
                {
                    until: null,
                },
            );
        });
    }

    const loginForm = getElement("member-login");
    loginForm?.addEventListener("submit", (event) => {
        event.preventDefault();
        const suspended = loginForm.dataset.suspend === "true";
        if (
            !confirm(
                suspended
                    ? "이 회원의 로그인을 정지하고 기존 세션을 종료할까요?"
                    : "로그인 정지를 해제할까요?",
            )
        )
            return;
        submit(
            loginForm,
            `/admin/member-accounts/${loginForm.dataset.memberId}/login-suspension`,
            "PATCH",
            { suspended },
        );
    });

    const roleForm = getElement("member-role");
    roleForm?.addEventListener("submit", (event) => {
        event.preventDefault();
        if (!confirm(`이 회원의 권한을 ${roleForm.elements.role.value}로 변경할까요?`)) return;
        submit(roleForm, `/admin/member-accounts/${roleForm.dataset.memberId}/role`, "PATCH", {
            role: roleForm.elements.role.value,
        });
    });

    createForm?.addEventListener("submit", (event) => {
        event.preventDefault();
        const body = Object.fromEntries(new FormData(createForm));
        if (body.password !== body.password_confirm) {
            message.textContent = "비밀번호 확인이 일치하지 않습니다.";
            message.dataset.error = "true";
            return;
        }
        delete body.password_confirm;
        submit(createForm, "/admin/member-accounts", "POST", body);
    });

    if (
        location.pathname.startsWith("/admin/members/") &&
        new URLSearchParams(location.search).has("saved")
    )
        message.textContent = "회원 정보를 저장했습니다.";
}

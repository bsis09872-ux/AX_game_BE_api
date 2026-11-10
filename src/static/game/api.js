export function createFishingApi(signal, navigate) {
    async function request(path, body) {
        const timeout = new AbortController();
        const timer = setTimeout(() => timeout.abort(), 8000);
        let response, data;
        try {
            response = await fetch(path, {
                method: "POST",
                credentials: "same-origin",
                redirect: "error",
                headers: { Accept: "application/json", "Content-Type": "application/json" },
                body: JSON.stringify(body),
                signal: AbortSignal.any([signal, timeout.signal]),
            });
            data = response.status === 204 ? null : await response.json();
            signal.throwIfAborted();
        } catch (cause) {
            signal.throwIfAborted();
            const error = new Error(
                "응답을 확인하지 못했습니다. 결과 확인을 누르거나 인벤토리를 확인해 주세요.",
                { cause },
            );
            error.uncertain = true;
            throw error;
        } finally {
            clearTimeout(timer);
        }

        if (!response.ok) {
            if (response.status === 401) navigate("/login?expired=1", { replace: true });

            const error = new Error(
                data?.detail?.message ||
                    "낚시 결과를 확인하지 못했습니다. 인벤토리를 확인해 주세요.",
            );
            error.retryAfter = Number(response.headers.get("Retry-After")) || 0;
            error.uncertain =
                response.status >= 500 &&
                !["FISHING_DISABLED", "FISHING_NO_REWARD"].includes(data?.detail?.code);
            throw error;
        }
        return data;
    }

    return {
        async beginCast(id, connectionId) {
            const start = performance.now();
            const data = await request("/v1/play/casts", { id, connection_id: connectionId });
            const halfRoundTrip = (performance.now() - start) / 2;
            return {
                ...data,
                biteDeadline:
                    performance.now() +
                    Date.parse(data.bite_at) -
                    Date.parse(data.server_time) -
                    halfRoundTrip,
            };
        },
        cancelCast: (id, connectionId) =>
            request("/v1/play/casts/cancel", { id, connection_id: connectionId }),
        async catchItem(id) {
            const data = await request("/v1/play/fishing-results", { cast_id: id });
            return {
                id: data.id,
                name: data.definition.name,
                category: data.definition.category,
                rarity: data.definition.rarity,
                icon: data.definition.icon,
            };
        },
    };
}

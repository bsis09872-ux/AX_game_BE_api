import { ensureSession } from "../auth-session.js";

// 페이지가 소켓/재접속/하트비트 수명을 소유한다. HTTP 지급 요청은 재접속으로 재전송하지 않는다.
export function createWorldConnection({ player, room, signal, navigate, status, onDisconnect }) {
    let socket, retryTimer, heartbeat;
    let sequence = 0,
        acknowledged = -1,
        attempts = 0,
        lastReply = 0;
    let connectionId = null;
    let stopped = false;
    const others = new Map();
    const waiting = new Set();

    function setStatus(text) {
        status.dataset.networkStatus = text;
    }

    function clearWaiters() {
        for (const waiter of waiting) waiter.reject(new Error("낚시터 연결을 확인해 주세요."));
        waiting.clear();
    }

    function sendMove() {
        if (!connectionId || socket?.readyState !== WebSocket.OPEN) return null;
        const seq = sequence++;
        socket.send(
            JSON.stringify({
                type: "move",
                seq,
                x: player.x,
                y: player.y,
                face: player.face,
                direction: player.dir,
                skin: player.skin,
                pose: player.pose || (player.walking ? "walk" : "idle"),
            }),
        );
        return seq;
    }

    function connect() {
        if (stopped || signal.aborted) return;
        setStatus("연결 중…");
        const protocol = location.protocol === "https:" ? "wss:" : "ws:";
        lastReply = performance.now();
        socket = new WebSocket(`${protocol}//${location.host}/v1/ws/world`);

        socket.onopen = () => {
            lastReply = performance.now();
            socket.send(JSON.stringify({ type: "hello", room, skin: player.skin }));
        };

        socket.onmessage = (event) => {
            if (signal.aborted) return;
            lastReply = performance.now();
            const message = JSON.parse(event.data);
            if (message.type === "welcome") {
                connectionId = message.connection_id;
                sequence = 0;
                acknowledged = -1;
                attempts = 0;
                player.x = message.x;
                player.y = message.y;
                player.walking = false;
                player.id = message.id;
                sendMove();
            } else if (message.type === "state") {
                const present = new Set();
                for (const remote of message.players) {
                    if (remote.id === player.id) {
                        acknowledged = Math.max(acknowledged, remote.seq);
                        continue;
                    }
                    present.add(remote.id);
                    const previous = others.get(remote.id);
                    others.set(remote.id, {
                        ...remote,
                        receivedAt: performance.now(),
                        fromX: previous?.drawX ?? remote.x,
                        fromY: previous?.drawY ?? remote.y,
                        drawX: previous?.drawX ?? remote.x,
                        drawY: previous?.drawY ?? remote.y,
                    });
                }
                for (const id of others.keys()) if (!present.has(id)) others.delete(id);
                for (const waiter of waiting) {
                    if (acknowledged >= waiter.seq) {
                        waiting.delete(waiter);
                        waiter.resolve(connectionId);
                    }
                }
                setStatus(`${message.players.length}명 접속`);
            } else if (message.type === "correct") {
                player.x = message.x;
                player.y = message.y;
                player.walking = false;
                onDisconnect();
            } else if (message.type === "error") {
                setStatus(message.message);
            }
        };

        socket.onclose = async (event) => {
            connectionId = null;
            others.clear();
            clearWaiters();
            onDisconnect();
            if (stopped || signal.aborted) return;
            if ([4409, 1008].includes(event.code)) {
                stopped = true;
                setStatus(
                    event.code === 4409
                        ? "다른 창에서 접속했습니다."
                        : "연결이 종료됐습니다. 새로고침해 주세요.",
                );
                return;
            }
            if (event.code === 4401) {
                try {
                    const session = await ensureSession(signal);
                    if (signal.aborted) return;
                    if (!session) {
                        stopped = true;
                        void navigate("/login?expired=1", { replace: true });
                        return;
                    }
                } catch {
                    if (signal.aborted) return;
                }
            }
            setStatus("재연결 중…");
            retryTimer = setTimeout(connect, Math.min(10000, 500 * 2 ** attempts++));
        };
    }

    heartbeat = setInterval(() => {
        if (socket?.readyState === WebSocket.CONNECTING && performance.now() - lastReply > 8000)
            socket.close();
        if (socket?.readyState === WebSocket.OPEN) {
            if (performance.now() - lastReply > 8000) socket.close();
            else sendMove();
        }
    }, 100);

    signal.addEventListener(
        "abort",
        () => {
            stopped = true;
            clearTimeout(retryTimer);
            clearInterval(heartbeat);
            clearWaiters();
            socket?.close(1000);
            others.clear();
        },
        { once: true },
    );

    return {
        others,
        connect,
        get message() {
            return status.dataset.networkStatus || "연결 중…";
        },
        get connected() {
            return !!connectionId;
        },
        async synchronize() {
            const seq = sendMove();
            if (seq === null) throw new Error("낚시터에 연결한 뒤 다시 시도해 주세요.");
            return new Promise((resolve, reject) => {
                const timer = setTimeout(() => {
                    waiting.delete(waiter);
                    reject(new Error("위치 확인이 지연되고 있습니다."));
                }, 2500);
                const waiter = {
                    seq,
                    resolve: (value) => {
                        clearTimeout(timer);
                        resolve(value);
                    },
                    reject: (error) => {
                        clearTimeout(timer);
                        reject(error);
                    },
                };
                waiting.add(waiter);
            });
        },
    };
}

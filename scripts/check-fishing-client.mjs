import assert from "node:assert/strict";
import { test } from "node:test";
import { Fishing } from "../src/static/game/fishing.js";
import { createFishingApi } from "../src/static/game/api.js";
import { createWorldConnection } from "../src/static/game/world-connection.js";

const world = {
    map: { innerWater: [[1, 1]] },
    nearLake: () => true,
    nearestWater: () => ({ x: 20, y: 20 }),
};

test("규약 위반과 중복 접속 종료는 자동 재접속하지 않는다", async () => {
    const originalLocation = globalThis.location;
    const originalSocket = globalThis.WebSocket;
    globalThis.location = { protocol: "https:", host: "qa.invalid" };
    try {
        for (const code of [1003, 1008, 1009, 4409]) {
            const sockets = [];
            globalThis.WebSocket = class {
                constructor() { sockets.push(this); }
                close() {}
            };
            const scope = new AbortController();
            try {
                const connection = createWorldConnection({
                    player: {}, room: "world", signal: scope.signal,
                    status: { dataset: {} }, onDisconnect() {}, navigate() {},
                });
                connection.connect();
                await sockets[0].onclose({ code });
                connection.connect();
                assert.equal(sockets.length, 1, `close code ${code}`);
                assert.equal(connection.connected, false);
            } finally { scope.abort(); }
        }
    } finally {
        globalThis.location = originalLocation;
        globalThis.WebSocket = originalSocket;
    }
});

function fishing(overrides = {}) {
    return new Fishing({
        player: { x: 0, y: 0, face: 1, dir: "down" }, world,
        api: {
            beginCast: async () => ({ biteDeadline: performance.now() + 2500 }),
            cancelCast: async () => {},
            catchItem: overrides.catchItem || (async () => ({ id: "1", name: "fish" })),
        },
        network: { connected: true, synchronize: async () => "connection" },
        signal: new AbortController().signal,
        enabled: true, random: () => 0,
        ...overrides,
    });
}

test("입질 전에 당기면 지급하지 않고, 백그라운드 경과 시간도 입질 만료에 반영한다", async () => {
    const game = fishing({ catchItem: () => assert.fail("unexpected grant") });
    game.act(); await game.cast(); game.update(550);
    assert.equal(game.state, "waiting");
    game.act();
    assert.equal(game.state, "missed");
    game.cooldownUntil = 0;
    await game.cast(); game.update(550);
    game.biteDeadline = performance.now() - 1500;
    game.update(1); game.update(1);
    assert.equal(game.state, "missed");
});

test("입질 연타는 요청 하나이며 응답을 받은 뒤에만 획득한다", async () => {
    let resolve, calls = 0;
    const game = fishing({ catchItem: () => { calls++; return new Promise((done) => resolve = done); } });
    game.act(); await game.cast(); game.update(550);
    game.biteDeadline = performance.now(); game.update(1);
    game.act(); game.act(); game.act(); game.update(700);
    assert.equal(calls, 1);
    assert.equal(game.state, "reeling");
    resolve({ id: "reward" });
    await Promise.resolve();
    game.update(1);
    assert.equal(game.state, "caught");
});

test("응답이 불확실하면 이동/재연결 후에도 동일 시도 ID로만 결과를 확인한다", async () => {
    const ids = [];
    const game = fishing({ catchItem: async id => {
        ids.push(id);
        if (ids.length === 1) throw Object.assign(new Error("timeout"), { uncertain: true });
        return { id: "same-reward" };
    } });
    game.castId = "same-cast";
    await game.reel();
    assert.equal(game.state, "uncertain");
    assert.equal(game.canMove, true);
    game.cancel(); game.disconnect();
    await game.reel(); game.update(700);
    assert.deepEqual(ids, ["same-cast", "same-cast"]);
    assert.equal(game.state, "caught");
});

test("이전 페이지의 늦은 응답을 새 상태에 반영하지 않는다", async () => {
    const controller = new AbortController();
    let resolve;
    const game = fishing({ signal: controller.signal, catchItem: () => new Promise((done) => resolve = done) });
    const request = game.reel();
    controller.abort();
    resolve({ id: "late" });
    await request;
    assert.equal(game.caught, null);
});

test("쿨다운 동안 재투척하지 않고 비활성화 시 요청하지 않는다", async () => {
    const game = fishing({ catchItem: async () => { throw Object.assign(new Error("cooldown"), { retryAfter: 10 }); } });
    await game.reel(); game.act();
    assert.equal(game.state, "missed");
    assert.ok(game.cooldownLeft > 0);
    const disabled = fishing({ enabled: false, catchItem: () => assert.fail("disabled grant") });
    disabled.act();
    assert.equal(disabled.state, "idle");
});

test("지급 API는 재시도 없이 서버 오류를 전달하고 토큰 헤더를 만들지 않는다", async () => {
    const original = globalThis.fetch;
    let calls = 0;
    globalThis.fetch = async (url, options) => {
        calls++;
        assert.equal(url, "/v1/play/fishing-results");
        assert.equal(options.credentials, "same-origin");
        assert.equal(options.headers.Authorization, undefined);
        return new Response(JSON.stringify({ detail: { message: "cooldown" } }), { status: 429, headers: { "Retry-After": "7" } });
    };
    try {
        await assert.rejects(createFishingApi(new AbortController().signal, () => {}).catchItem("same-cast"), (error) => error.retryAfter === 7);
        assert.equal(calls, 1);
    } finally { globalThis.fetch = original; }
});

const footPosition = (player) => ({ x: player.x + 8, y: player.y + 13 });

export class Fishing {
    constructor({ player, world, api, network, signal, enabled, random = Math.random }) {
        Object.assign(this, { player, world, api, network, signal, enabled, random });
        this.state = "idle";
        this.clock = 0;
        this.since = 0;
        this.bobber = null;
        this.caught = null;
        this.cooldownUntil = 0;
        this.note = "";
        this.noteUntil = 0;
    }

    get elapsed() {
        return this.clock - this.since;
    }
    get canMove() {
        return !["preparing", "reeling", "caught"].includes(this.state);
    }
    get cooldownLeft() {
        return Math.max(0, Math.ceil((this.cooldownUntil - Date.now()) / 1000));
    }

    setState(state, message = "") {
        this.state = state;
        this.since = this.clock;
        this.message = message;
    }

    flash(message) {
        this.note = message;
        this.noteUntil = this.clock + 2500;
    }

    cancel() {
        // 결과가 불확실한 시도는 이동해도 보존하여 같은 ID로 조회한다.
        if (["uncertain", "reeling"].includes(this.state)) return;
        this.cancelAttempt();
        this.bobber = null;
        this.setState("idle");
    }

    cancelAttempt() {
        if (this.castId && this.connectionId) {
            void this.api.cancelCast(this.castId, this.connectionId).catch(() => {});
        }
        this.castId = null;
    }

    disconnect() {
        if (["reeling", "uncertain", "caught"].includes(this.state)) return;
        this.castId = null;
        this.bobber = null;
        this.setState("idle");
    }

    async cast() {
        this.bobber = this.castTarget();
        if (!this.bobber) return;
        this.setState("preparing");
        const id = crypto.randomUUID();
        try {
            this.connectionId = await this.network.synchronize();
            if (this.state !== "preparing" || this.signal.aborted) return;
            this.castId = id;
            const attempt = await this.api.beginCast(id, this.connectionId);
            if (this.signal.aborted) return;
            if (this.castId !== id || this.state !== "preparing") return;
            this.biteDeadline = attempt.biteDeadline;
            this.cooldownUntil = Date.now() + 10000;
            this.setState("casting");
        } catch (error) {
            if (this.signal.aborted || this.state !== "preparing") return;
            this.cancelAttempt();
            this.bobber = null;
            this.cooldownUntil = Date.now() + (error.retryAfter || 0) * 1000;
            this.setState(
                "missed",
                error.uncertain
                    ? "투척을 확인하지 못했습니다. 잠시 후 다시 시도해 주세요."
                    : error.message,
            );
        }
    }

    again() {
        if (this.state !== "caught") return;
        this.caught = null;
        this.castId = null;
        this.bobber = null;
        this.setState("rodOut");
    }

    act() {
        if (!this.enabled)
            return this.flash(
                "낚시 보상이 비활성화되어 있습니다. 이동과 캐릭터 선택은 가능합니다.",
            );

        if (this.state === "uncertain") return void this.reel();
        if (!this.network.connected) return this.flash("낚시터에 연결 중입니다.");

        switch (this.state) {
            case "idle":
                if (!this.world.nearLake(this.player)) return this.flash("호숫가로 이동해 주세요.");
                this.setState("rodOut");
                break;
            case "rodOut":
            case "missed":
                if (this.cooldownLeft) return;
                void this.cast();
                break;
            case "waiting":
                this.cancelAttempt();
                this.bobber = null;
                this.setState("missed", "너무 일찍 당겼어요. 다시 던져 보세요.");
                break;
            case "bite":
                this.reel();
                break;
        }
    }

    update(delta) {
        this.clock += delta;
        if (this.state === "casting" && this.elapsed >= 550) {
            this.setState("waiting");
        } else if (this.state === "waiting" && performance.now() >= this.biteDeadline) {
            this.setState("bite");
        } else if (this.state === "bite" && performance.now() > this.biteDeadline + 1000) {
            this.bobber = null;
            this.cancelAttempt();
            this.setState("missed", "놓쳤어요. 다시 던져 보세요.");
        } else if (this.state === "reeling" && this.elapsed >= 700 && this.caught) {
            this.setState("caught");
        }
    }

    async reel() {
        // 상태를 먼저 바꾸어 클릭 연타가 지급 요청 여러 건으로 이어지지 않게 한다.
        this.setState("reeling");
        try {
            const item = await this.api.catchItem(this.castId);
            this.signal.throwIfAborted();
            this.caught = item;
        } catch (error) {
            if (this.signal.aborted) return;
            this.bobber = null;
            this.cooldownUntil = Date.now() + (error.retryAfter || 0) * 1000;
            this.setState(
                error.uncertain ? "uncertain" : "missed",
                error.message || "결과를 확인하지 못했습니다. 인벤토리를 확인해 주세요.",
            );
        }
    }

    castTarget() {
        const foot = footPosition(this.player);
        const pool = this.world.map.innerWater.map(([column, row]) => ({
            x: column * 16 + 8,
            y: row * 16 + 8,
        }));
        const ring = pool.filter((point) => {
            const distance = Math.hypot(point.x - foot.x, point.y - foot.y);
            return distance >= 24 && distance <= 64;
        });
        const ahead = ring.filter((point) =>
            this.player.dir === "up"
                ? point.y < foot.y - 4
                : this.player.dir === "down"
                  ? point.y > foot.y + 4
                  : (point.x - foot.x) * this.player.face > 4,
        );
        const candidates = ahead.length ? ahead : ring;
        const point = candidates.length
            ? candidates[Math.floor(this.random() * candidates.length)]
            : this.world.nearestWater(this.player);
        return point ? { x: Math.round(point.x - 8), y: Math.round(point.y - 9) } : null;
    }

    prompt() {
        if (this.clock < this.noteUntil) return this.note;
        if (!this.enabled) return "낚시 보상 비활성 / WASD, 방향키로 이동";
        if (this.cooldownLeft && ["rodOut", "missed"].includes(this.state))
            return `${this.cooldownLeft}초 뒤 다시 던질 수 있어요.`;

        return {
            idle: this.world.nearLake(this.player)
                ? "클릭 또는 스페이스: 낚싯대 꺼내기"
                : "WASD, 방향키로 호숫가까지 이동",
            rodOut: "클릭 또는 스페이스: 찌 던지기",
            preparing: "투척 준비 중…",
            uncertain: "응답을 확인하지 못했습니다. 결과 확인을 눌러 주세요.",
            casting: "찌를 던지는 중…",
            waiting: "입질을 기다리세요. 느낌표가 뜨면 클릭!",
            bite: "지금 클릭!",
            reeling: "끌어올리는 중…",
            caught: "낚았다!",
            missed: this.message || "다시 던져 보세요.",
        }[this.state];
    }
}

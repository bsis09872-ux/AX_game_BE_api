// 오프닝 화면 (templates/game/opening.html). 캔버스 하나에 매 프레임 장면을 다시 그린다.
// 순서: 빨간 커튼이 끈 높이부터 양옆으로 묶여 걷힘 → 낚싯줄 → 입질 → 로고가 튀어 올랐다 무대 가운데로 떨어져 통통 → PRESS START
// 내부 좌표는 480×270(게임 타일 16px 기준)이고, 실제 캔버스는 화면 크기에 맞춰 k배로 키워 그린다.
// 팀 공통 화면 규칙: 동작은 initOpeningPage로 pages.js에 "opening"으로 등록하고, 화면을 떠나면(signal) 멈춘다.
export function initOpeningPage({ root, signal, navigate }) {
  if (!root.querySelector('#opening-cv')) return;
  // ---------- 무대 크기: 내부 좌표 480×270 (게임 타일 16px 기준), 실제 픽셀은 화면 크기에 맞춰 선명하게 ----------
  const W = 480, H = 270;
  const stage = root.querySelector('#opening-stage'), cv = root.querySelector('#opening-cv'), ctx = cv.getContext('2d');
  let k = 1;
  function fit() {
    const r = cv.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    cv.width = Math.round(r.width * dpr); cv.height = Math.round(r.height * dpr);
    k = cv.width / W;
  }
  addEventListener('resize', fit, { signal });

  // ---------- 그림 ----------
  const S = '/static/sprites';
  const SPRITES = {
    char_player: `${S}/characters/char_player.png`, char_auctioneer: `${S}/characters/char_auctioneer.png`,
    ui_podium: `${S}/ui/ui_podium.png`, ui_gavel: `${S}/ui/ui_gavel.png`, item_fish_mackerel: `${S}/item_fish_mackerel.png`,
    ...Object.fromEntries(Array.from({ length: 14 }, (_, i) => [`audience_${i}`, `${S}/audience/audience_${i}.png`])),
  };
  const img = {};
  const load = (src) => new Promise((ok) => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => ok(null); i.src = src; });
  const ready = Promise.all([
    ...Object.entries(SPRITES).map(async ([key, src]) => { img[key] = await load(src); }),
    load('/static/images/catch-and-bid-logo-opening.png').then((i) => { img.logo = i; }),
    document.fonts ? document.fonts.load('700 10px Galmuri11').catch(() => {}) : null,
  ]);

  // ---------- 장면 배치 (내부 좌표) ----------
  const LAKE = { x0: 0, x1: 352, top: 150, bottom: 186 };   // 호수
  const SURFACE = 166;                                       // 로고가 솟아오르는 물 높이
  const DOCK = { top: 186, bottom: 200 };                    // 나무 선착장
  const LOGO_W = 250, LOGO_H = 125;                          // 로고 크기
  const HOOK = { u: 0.733, v: 0.338 };                       // 로고 그림 안의 낚싯바늘 위치(비율). 줄이 여기에 걸린다
  const PIVOT_X = 240 - LOGO_W / 2 + HOOK.u * LOGO_W;        // 찌가 떨어지는 곳 = 다 떨어진 로고의 바늘 x (로고 가운데 x=240)
  const ROD_TIP = { x: PIVOT_X + 30, y: -6 };                // 화면 위 바깥의 낚싯대 끝

  // 관객: 4줄, 줄마다 반 칸씩 엇갈리게. 사람마다 그림·박자를 정해 둔다
  const crowd = [];
  for (let row = 0; row < 4; row++) {
    for (let i = -1; i < 17; i++) {
      crowd.push({ x: i * 30 + (row % 2 ? 15 : 0) + ((i * 7 + row * 3) % 5), y: 204 + row * 17, sprite: (i * 5 + row * 3 + 14) % 14, phase: (i * 1.7 + row) % 6.28 });
    }
  }

  // ---------- 시간표 (ms) ----------
  const T = { curtainUp: 600, curtainDone: 2800, castStart: 1900, castDone: 2600, nibble1: 2900, nibble2: 3250, yank: 3600, settle: 5600, title: 4700 };
  const ease = { inOut: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2), out: (t) => 1 - Math.pow(1 - t, 3) };
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const prog = (t, a, b) => clamp((t - a) / (b - a));

  // ---------- 그리기 도구 ----------
  const rect = (x, y, w, h, c) => { ctx.fillStyle = c; ctx.fillRect(x, y, w, h); };
  const sprite = (key, x, y, s = 2, flip = false) => {
    const i = img[key]; if (!i) return;
    ctx.save(); ctx.imageSmoothingEnabled = false;
    if (flip) { ctx.translate(Math.round(x) + 16 * s, Math.round(y)); ctx.scale(-1, 1); ctx.drawImage(i, 0, 0, 16 * s, 16 * s); }
    else ctx.drawImage(i, Math.round(x), Math.round(y), 16 * s, 16 * s);
    ctx.restore();
  };
  function disc(cx, cy, r, c) { // 픽셀 원: 줄마다 사각형
    ctx.fillStyle = c;
    for (let y = -r; y <= r; y++) { const h = Math.round(Math.sqrt(r * r - y * y)); ctx.fillRect(cx - h, cy + y, h * 2, 1); }
  }

  // ---------- 배경: 해 질 녘 호숫가 경매장 ----------
  function drawBackground(t) {
    const sky = ['#f39a3b', '#f5a640', '#f7b546', '#f9c34f', '#fbd05a', '#fcdc6a', '#fde67c'];
    sky.forEach((c, i) => rect(0, i * 16, W, 17, c));
    disc(408, 70, 26, '#fff1a6'); disc(408, 70, 20, '#fff8cf');
    // 구름: 천천히 흐른다
    const cloud = (x, y, s) => { rect(x, y, 34 * s, 6 * s, '#fff0c8'); rect(x + 6 * s, y - 4 * s, 18 * s, 5 * s, '#fff0c8'); rect(x + 4 * s, y + 6 * s, 26 * s, 2 * s, '#f6d9a0'); };
    const drift = (t / 260) % 560;
    cloud(((60 + drift) % 560) - 60, 30, 1.2); cloud(((250 + drift * 0.7) % 560) - 60, 18, 0.9); cloud(((420 + drift * 0.5) % 560) - 60, 46, 0.8);
    // 새
    for (const [bx, by] of [[90, 52], [104, 46], [300, 40]]) { const f = Math.floor(t / 250 + bx) % 2; rect(bx, by + f, 3, 1, '#7a4a3a'); rect(bx + 3, by + 1 - f, 3, 1, '#7a4a3a'); }
    // 나무 줄
    for (let x = -8; x < W + 16; x += 22) {
      const h = 18 + ((x * 13) % 9);
      rect(x + 9, 136 - 6, 4, 12, '#6b3f2a');
      disc(x + 11, 122 - h / 3, 12, '#2f7a3a'); disc(x + 11, 116 - h / 3, 9, '#3f9a48'); rect(x + 6, 108 - h / 3, 4, 3, '#63b85a');
    }
    // 빨간 버섯
    for (const mx of [60, 132, 318]) { rect(mx, 140, 2, 4, '#f3e1c6'); rect(mx - 2, 137, 6, 3, '#d43c3c'); rect(mx, 138, 1, 1, '#fff'); }
    rect(0, 138, W, 14, '#7cc15e'); rect(0, 138, W, 2, '#95d070');
    // 호수
    rect(LAKE.x0, LAKE.top, LAKE.x1 - LAKE.x0, LAKE.bottom - LAKE.top, '#4fb8e8');
    rect(LAKE.x0, LAKE.top, LAKE.x1 - LAKE.x0, 3, '#e8d39c'); rect(LAKE.x1, LAKE.top, 4, LAKE.bottom - LAKE.top, '#e8d39c');
    for (let i = 0; i < 14; i++) { // 물결 반짝
      const sx = (i * 47 + Math.floor(t / 90)) % (LAKE.x1 - 20) + 6, sy = LAKE.top + 7 + (i * 11) % 26;
      if ((Math.floor(t / 400) + i) % 3) rect(sx, sy, 6, 1, '#bfeaff');
    }
    // 오른쪽: 흙길과 경매장 건물
    rect(356, 152, W - 356, 34, '#7cc15e');
    rect(380, 166, 100, 12, '#c99a62'); rect(380, 166, 100, 2, '#ddb57c');
    const bx = 372, by = 92;
    rect(bx, by, 100, 76, '#a8443a');
    for (let y = 0; y < 5; y++) for (let x = 0; x < 9; x++) rect(bx + 4 + x * 11 + (y % 2) * 5, by + 6 + y * 8, 7, 5, (x + y) % 3 ? '#c4573f' : '#8f3530'); // 지붕 무늬
    rect(bx, by + 44, 100, 32, '#c77a4d'); for (let y = 0; y < 4; y++) rect(bx, by + 46 + y * 8, 100, 1, '#a75e3c');
    rect(bx + 62, by + 50, 18, 26, '#3c2620'); rect(bx + 64, by + 52, 14, 24, '#20140f');
    rect(bx - 4, by - 4, 108, 6, '#7a2e29');
    // BID 간판
    rect(352, 126, 30, 18, '#f1e0bd'); rect(352, 126, 30, 2, '#5a3a2a'); rect(352, 142, 30, 2, '#5a3a2a'); rect(365, 144, 3, 12, '#5a3a2a');
    ctx.fillStyle = '#5a3a2a'; ctx.font = '700 9px Galmuri11, monospace'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('BID', 367, 135);
    // 선착장
    rect(0, DOCK.top, W, DOCK.bottom - DOCK.top, '#b9743e');
    for (let x = 0; x < W; x += 12) rect(x, DOCK.top, 1, DOCK.bottom - DOCK.top, '#8a5129');
    rect(0, DOCK.top, W, 2, '#d99355'); rect(0, DOCK.bottom - 2, W, 2, '#7a4523');
    // 관객석 바닥(갈색). 매 장면 다시 칠해서 지난 장면의 잔상이 남지 않게 한다
    rect(0, DOCK.bottom, W, H - DOCK.bottom, '#4a2b20');
  }

  // ---------- 무대 위 사람들 ----------
  function drawCast(t) {
    const cheer = t > T.yank;
    const hop = (ph) => (cheer ? Math.max(0, Math.sin(t / 140 + ph)) * 4 : 0);
    // 낚시꾼: 물고기를 들고 있다가 로고가 튀어 오르면 만세
    const ay = DOCK.top - 30 - hop(0.5);
    sprite('char_player', 52, ay);
    sprite('item_fish_mackerel', cheer ? 56 : 74, cheer ? ay - 22 : ay + 4, 2, false);
    // 경매사와 단상
    sprite('char_auctioneer', 404, DOCK.top - 34 - (cheer ? Math.max(0, Math.sin(t / 200)) * 2 : 0));
    sprite('ui_podium', 404, DOCK.top - 24);
    if (cheer && Math.floor(t / 300) % 2) sprite('ui_gavel', 430, DOCK.top - 46, 1);
  }
  function drawCrowd(t) {
    const cheer = t > T.yank;
    for (const p of crowd) {
      const bob = cheer ? Math.max(0, Math.sin(t / 150 + p.phase)) * 5 : Math.sin(t / 700 + p.phase) * 0.6;
      sprite('audience_' + p.sprite, p.x, p.y - bob);
    }
    // 객석 앞쪽 그늘
    const g = ctx.createLinearGradient(0, 236, 0, H); g.addColorStop(0, 'rgba(29,20,24,0)'); g.addColorStop(1, 'rgba(29,20,24,.55)');
    ctx.fillStyle = g; ctx.fillRect(0, 236, W, H - 236);
  }

  // ---------- 낚싯줄·찌·물결 ----------
  const ripples = [];
  const splash = [];
  function addRipple(x, t) { ripples.push({ x, t0: t }); }
  function addSplash(t) {
    for (let i = 0; i < 70; i++) {
      const x = PIVOT_X - HOOK.u * LOGO_W + Math.random() * LOGO_W;
      splash.push({ x, y: SURFACE, vx: (Math.random() - 0.5) * 70, vy: -60 - Math.random() * 120, t0: t, c: ['#ffffff', '#d9f7ff', '#9fdcf2'][i % 3] });
    }
  }
  function drawRipples(t) {
    for (const r of ripples) {
      const a = (t - r.t0) / 900; if (a < 0 || a > 1) continue;
      const rx = 6 + a * 34, ry = 2 + a * 6; ctx.strokeStyle = `rgba(232,250,255,${1 - a})`; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.ellipse(r.x, SURFACE + 1, rx, ry, 0, 0, Math.PI * 2); ctx.stroke();
    }
  }
  function drawSplash(t, dt) {
    for (const p of splash) {
      const s = (t - p.t0) / 1000; if (s < 0 || s > 1.4) continue;
      const x = p.x + p.vx * s, y = p.y + p.vy * s + 160 * s * s;
      if (y > SURFACE + 2) continue;
      rect(Math.round(x), Math.round(y), 2, 2, p.c);
    }
  }
  function line(from, to, sag) {
    ctx.strokeStyle = '#3f2631'; ctx.lineWidth = 0.8;
    ctx.beginPath(); ctx.moveTo(from.x, from.y);
    ctx.quadraticCurveTo((from.x + to.x) / 2 + sag, (from.y + to.y) / 2, to.x, to.y); ctx.stroke();
  }
  function bobber(x, y) { rect(x - 2, y - 4, 5, 4, '#e8413c'); rect(x - 2, y, 5, 3, '#ffffff'); rect(x, y - 7, 1, 3, '#3f2631'); }

  // ---------- 로고(4·5안): 줄에 걸려 물에서 높이 튀어 오른 뒤, 줄이 풀리며 무대 가운데로 떨어져 통통 튄다 ----------
  const LOGO_X = 240 - LOGO_W / 2;  // 다 떨어진 뒤 로고 왼쪽 (무대 가운데)
  const REST_TOP = 66;              // 다 떨어진 뒤 로고 위쪽. 아래 끝이 선착장 바로 위에 온다
  const APEX_TOP = -10;             // 가장 높이 튀어 오른 곳 (위 장식막 뒤로 살짝 들어간다)
  const RISE = 0.42, FALL = 0.48;   // 튀어 오르는 시간, 꼭대기에서 떨어지는 시간 (초)
  const G = (2 * (REST_TOP - APEX_TOP)) / (FALL * FALL); // 떨어지는 가속도 (px/s²)
  const V_HIT = G * FALL;           // 처음 바닥에 닿는 속도
  const BOUNCE = 0.42;              // 튈 때마다 남는 속도 비율
  const START_TOP = SURFACE + 6;    // 물속에 잠겨 있을 때 로고 위쪽
  function logoPose(t) {
    const s = (t - T.yank) / 1000;
    const wobble = (k) => 0.1 * Math.exp(-k * 2.2) * Math.sin(k * 11);
    if (s < 0) return { top: START_TOP, angle: 0, sx: 1, sy: 1, hooked: true, landed: -1 };
    if (s < RISE) { // 줄에 끌려 휙 올라온다 (세로로 살짝 늘어난다)
      const k = s / RISE, top = START_TOP + (APEX_TOP - START_TOP) * ease.out(k);
      return { top, angle: wobble(s), sx: 0.96, sy: 1.06, hooked: true, landed: -1 };
    }
    if (s < RISE + FALL) { // 줄이 풀려 떨어진다
      const f = s - RISE;
      return { top: APEX_TOP + 0.5 * G * f * f, angle: wobble(s), sx: 1, sy: 1, hooked: false, landed: -1 };
    }
    // 바닥에 닿을 때마다 BOUNCE배 속도로 다시 튄다. 닿은 순간에는 납작하게 눌렸다 펴진다
    let f = s - RISE - FALL, v = V_HIT * BOUNCE, hit = V_HIT, top = REST_TOP;
    while (v > 14 && f > (2 * v) / G) { f -= (2 * v) / G; hit = v; v *= BOUNCE; }
    if (v > 14) top = REST_TOP - (v * f - 0.5 * G * f * f);
    const squash = 0.16 * (hit / V_HIT) * Math.exp(-f * 16) * Math.cos(f * 38);
    return { top, angle: wobble(s) * Math.exp(-f * 4), sx: 1 + squash, sy: 1 - squash, hooked: false, landed: s - RISE - FALL };
  }
  function drawLogo(t) {
    const i = img.logo; if (!i) return null;
    const pose = logoPose(t);
    ctx.save();
    if (pose.hooked) { ctx.beginPath(); ctx.rect(0, -60, W, SURFACE + 60); ctx.clip(); } // 물 위로 나온 부분만 보인다
    ctx.translate(LOGO_X + LOGO_W / 2, pose.top + LOGO_H); // 아래 가운데를 기준으로 눌리고 기운다
    ctx.rotate(pose.angle); ctx.scale(pose.sx, pose.sy);
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(i, -LOGO_W / 2, -LOGO_H, LOGO_W, LOGO_H);
    ctx.restore();
    return pose;
  }
  // 줄: 끌어올리는 동안은 로고 속 낚싯바늘에 걸려 있고, 꼭대기에서 풀리면 낚싯대 쪽으로 감겨 올라간다
  function drawLogoLine(t, pose) {
    if (!pose || t < T.yank) return;
    const s = (t - T.yank) / 1000;
    const hookAt = (top) => ({ x: LOGO_X + HOOK.u * LOGO_W, y: top + HOOK.v * LOGO_H });
    if (pose.hooked) return line(ROD_TIP, hookAt(pose.top), 0);
    const r = (s - RISE) / 0.3;
    if (r >= 1) return;
    const from = hookAt(APEX_TOP), end = { x: from.x + (ROD_TIP.x - from.x) * ease.out(r), y: from.y + (ROD_TIP.y - from.y) * ease.out(r) };
    line(ROD_TIP, end, 4 * (1 - r));
    rect(Math.round(end.x) - 1, Math.round(end.y), 3, 3, '#9aa3ad'); // 빈 바늘
  }
  // 처음 바닥에 닿을 때 양옆으로 먼지가 퍼진다
  function drawDust(t, pose) {
    if (!pose || pose.landed < 0 || pose.landed > 0.5) return;
    const a = pose.landed / 0.5, y = REST_TOP + LOGO_H - 2;
    for (let n = 0; n < 6; n++) {
      const side = n % 2 ? 1 : -1, dist = 10 + a * (26 + n * 6);
      const x = 240 + side * (LOGO_W / 2 - 30 + dist), yy = y - a * (6 + (n % 3) * 4), s = Math.max(1, Math.round(4 * (1 - a)));
      ctx.globalAlpha = 1 - a; rect(Math.round(x), Math.round(yy), s, s, '#f3e1c6'); ctx.globalAlpha = 1;
    }
  }
  function drawSparkles(t) {
    if (t < T.settle - 400) return;
    for (let n = 0; n < 7; n++) {
      const ph = Math.floor((t - T.settle) / 260) + n * 3;
      if (ph % 4 === 0) continue;
      const x = 112 + ((n * 67 + ph * 13) % 256), y = 58 + ((n * 41 + ph * 7) % 126), s = ph % 4 === 2 ? 3 : 2;
      rect(x - s, y, s * 2 + 1, 1, '#fff6c2'); rect(x, y - s, 1, s * 2 + 1, '#fff6c2'); rect(x, y, 1, 1, '#ffffff');
    }
  }
  // PRESS START(5안): 로고가 자리 잡은 뒤 0.5초마다 통째로 나타났다 사라진다. 반투명 없이 딱딱 끊어지고, 커튼보다 위에 그린다
  function drawPressStart(t) {
    if (t < T.settle || Math.floor((t - T.settle) / 500) % 2) return;
    ctx.save();
    ctx.font = '700 11px Galmuri11, monospace'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    const msg = 'PRESS START · 아무 키나 눌러 입장';
    const w = ctx.measureText(msg).width + 16;
    rect(240 - w / 2, 196, w, 15, '#24191f'); rect(240 - w / 2, 196, w, 1, '#f2b84b'); rect(240 - w / 2, 210, w, 1, '#f2b84b');
    ctx.fillStyle = '#fff4dc'; ctx.fillText(msg, 240, 204);
    ctx.restore();
  }

  // ---------- 커튼(5안): 픽셀 두 막이 끈 높이부터 양옆으로 당겨져 모래시계 모양으로 묶이고, 위 장식막은 위로 걷힌다 ----------
  // 다 걷힌 모양: 위는 50px, 끈(TIE_Y)에서 22px로 잘록, 아래로 다시 50px까지 퍼진다. 색은 1안 벨벳 4단계 + 금술만 쓴다
  // 줄마다 폭이 매끄러운 함수라서 가장자리가 들쭉날쭉하지 않다
  const hex = (h) => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  const VELVET = ['#4d0a1a', '#6c0f25', '#901631', '#b3203a', '#d8344c'].map(hex); // 0 = 가장 어두운 접힘선, 4 = 빛
  const GOLD = ['#a8701f', '#e3a23c', '#ffd47a'].map(hex);
  const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map((v) => (v + 0.5) / 16); // 4×4 점묘
  const TIE_Y = 150, CLOSED = W / 2 + 2, FOLDS = 7;
  const buf = document.createElement('canvas'); buf.width = W; buf.height = H;
  const bctx = buf.getContext('2d'), pix = bctx.createImageData(W, H);
  function put(x, y, c) { const i = (y * W + x) * 4; pix.data[i] = c[0]; pix.data[i + 1] = c[1]; pix.data[i + 2] = c[2]; pix.data[i + 3] = 255; }
  // 다 묶인 뒤 한쪽 막의 폭
  function tiedWidth(y) {
    if (y <= TIE_Y) { const s = y / TIE_Y; return 22 + 28 * (1 - s * s); }
    return 22 + 28 * Math.pow((y - TIE_Y) / (H - TIE_Y), 1.3);
  }
  // 열리는 중의 폭: 끈 높이가 먼저 당겨지고, 위아래는 조금 늦게 따라온다. 묶인 뒤에는 천이 한두 번 출렁인다
  function drapeWidth(y, p, t) {
    const far = Math.min(1, Math.abs(y - TIE_Y) / TIE_Y), delay = 0.22 * far;
    const q = ease.inOut(clamp((p - delay) / (1 - 0.22)));
    const after = t - T.curtainDone;
    const jiggle = after > 0 ? Math.exp(-after / 380) * Math.sin(after / 75) * 3 * far : 0;
    return CLOSED + (tiedWidth(y) - CLOSED) * q + jiggle;
  }
  function paintDrapes(p, t) {
    pix.data.fill(0);
    for (let y = 0; y < H; y++) {
      const w = drapeWidth(y, p, t), wi = Math.round(w);
      const shade = clamp(1 - y / 60), light = clamp((y - (H - 50)) / 50);
      for (let x = 0; x < wi; x++) {
        let c;
        if (y >= H - 6) c = y >= H - 2 ? GOLD[0] : GOLD[1];          // 아랫단 금술
        else if (wi - x <= 2) c = VELVET[0];                          // 안쪽 끝 진한 선
        else {
          const s = 0.5 + 0.5 * Math.sin(((x + 0.5) / w) * FOLDS * Math.PI * 2); // 주름은 폭에 맞춰 모인다
          let level = s > 0.82 ? 4 : s > 0.55 ? 3 : s > 0.25 ? 2 : 1;
          const d = BAYER[(y & 3) * 4 + (x & 3)];
          if (shade * 0.9 > d) level -= 1;  // 위는 그늘
          if (light * 0.7 > d) level += 1;  // 아래는 빛
          c = VELVET[Math.max(1, Math.min(4, level))];
        }
        put(x, y, c);
        put(W - 1 - x, y, c);
      }
    }
    bctx.putImageData(pix, 0, 0);
    ctx.save(); ctx.imageSmoothingEnabled = false; ctx.drawImage(buf, 0, 0, W, H); ctx.restore();
  }
  // 금색 끈과 술: 끈 높이가 거의 다 당겨지면 막을 감아 묶는다
  function drawTieback(p, t) {
    const q = ease.inOut(clamp(p / (1 - 0.22)));
    if (q < 0.75) return;
    const w = Math.round(drapeWidth(TIE_Y, p, t));
    for (const right of [false, true]) {
      const x = right ? W - w - 2 : 0;
      rect(x, TIE_Y - 2, w + 2, 5, '#e3a23c'); rect(x, TIE_Y - 2, w + 2, 1, '#ffd47a'); rect(x, TIE_Y + 2, w + 2, 1, '#a8701f');
      for (let k = 0; k < w; k += 4) rect(x + k + 1, TIE_Y - 1, 1, 3, '#c98a2c'); // 꼰 밧줄 무늬
      const tx = right ? W - w - 5 : w + 1;                                       // 술: 끈 끝에서 늘어진다
      rect(tx + 1, TIE_Y + 3, 1, 10, '#c98a2c');
      rect(tx - 1, TIE_Y + 13, 5, 4, '#ffd47a');
      rect(tx - 2, TIE_Y + 17, 7, 11, '#e3a23c'); rect(tx - 2, TIE_Y + 17, 7, 1, '#ffd47a');
      for (let k = 0; k < 7; k += 2) rect(tx - 2 + k, TIE_Y + 20, 1, 8, '#a8701f');
    }
  }
  function velvet(x0, y0, w, h, f) { // 1안 장식막용 세로 주름
    const C = ['#6c0f25', '#901631', '#b3203a', '#d8344c'];
    for (let x = 0; x < w; x += 2) {
      const s = 0.5 + 0.5 * Math.sin((x0 + x) / f);
      rect(x0 + x, y0, 2, h, C[s > 0.82 ? 3 : s > 0.55 ? 2 : s > 0.25 ? 1 : 0]);
    }
  }
  function fringe(x0, y, w) {
    rect(x0, y, w, 4, '#e3a23c'); rect(x0, y, w, 1, '#ffd47a');
    for (let x = x0; x < x0 + w; x += 6) { rect(x + 2, y + 4, 2, 4, '#c98a2c'); rect(x + 1, y + 8, 4, 2, '#e3a23c'); }
  }
  function drawCurtain(t) {
    const p = prog(t, T.curtainUp, T.curtainDone);
    paintDrapes(p, t);
    drawTieback(p, t);
    // 닫혀 있을 때 가운데 스포트라이트가 천천히 흔들린다
    if (p < 1) {
      const sx = W / 2 + Math.sin(t / 500) * 70, a = 0.22 * (1 - ease.inOut(p));
      const g = ctx.createRadialGradient(sx, H * 0.55, 4, sx, H * 0.55, 120);
      g.addColorStop(0, `rgba(255,236,190,${a})`); g.addColorStop(1, 'rgba(255,236,190,0)');
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    }
    // 위 장식막(밸런스): 1안 모양 그대로. 움직이지 않고 처음부터 끝까지 무대 위쪽 틀로 남는다
    velvet(0, 0, W, 16, 6);
    for (let x = 0; x < W; x += 40) for (let dx = 0; dx < 40; dx += 2) { const h = Math.round(6 * Math.sin((dx / 40) * Math.PI)); rect(x + dx, 16, 2, h, '#901631'); }
    fringe(0, 16, W);
  }

  // ---------- 한 장면 그리기 ----------
  let t = 0, last = 0, startedAt = 0, nibbled = new Set(), splashed = false, raf = 0;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  function frame(now) {
    const dt = last ? Math.min(now - last, 100) : 16;
    last = now;
    t += dt;

    // 이벤트: 입질 물결, 챔질 물보라
    if (t >= T.castDone && !nibbled.has('land')) { nibbled.add('land'); addRipple(PIVOT_X, t); }
    for (const n of [T.nibble1, T.nibble2]) if (t >= n && !nibbled.has(n)) { nibbled.add(n); addRipple(PIVOT_X, t); }
    if (t >= T.yank && !splashed) { splashed = true; addSplash(t); addRipple(PIVOT_X - 40, t); addRipple(PIVOT_X + 30, t + 60); }

    ctx.setTransform(k, 0, 0, k, 0, 0);
    ctx.imageSmoothingEnabled = false;
    drawBackground(t);
    drawRipples(t);
    drawCast(t);

    // 줄: 던지는 중(찌가 내려옴) → 찌가 물에 떠서 입질 → 챔질 뒤 로고 바늘에 팽팽하게
    const castP = ease.out(prog(t, T.castStart, T.castDone));
    if (t >= T.castStart && t < T.yank) {
      let by = ROD_TIP.y + (SURFACE - 2 - ROD_TIP.y) * castP;
      if (t >= T.castDone) {
        const n1 = Math.max(0, 1 - Math.abs(t - T.nibble1) / 160), n2 = Math.max(0, 1 - Math.abs(t - T.nibble2) / 160);
        by = SURFACE - 2 + Math.sin(t / 220) + 4 * Math.max(n1, n2) + (t > T.yank - 200 ? 6 : 0);
      }
      line(ROD_TIP, { x: PIVOT_X, y: by - 7 }, 6 * (1 - castP) + 2);
      bobber(PIVOT_X, by);
    }
    const pose = drawLogo(t);
    drawLogoLine(t, pose);
    drawDust(t, pose);
    drawSplash(t, dt);
    drawSparkles(t);
    drawCrowd(t);
    drawCurtain(t);
    drawPressStart(t);

    if (!signal.aborted) raf = requestAnimationFrame(frame);
  }

  function restart() {
    t = reduce ? T.settle + 600 : 0; last = 0; nibbled = new Set(); splashed = reduce; ripples.length = 0; splash.length = 0;
  }
  // 키나 클릭: 오프닝 중이면 마지막 장면으로 건너뛰고, PRESS START가 뜬 뒤면 낚시터로 들어간다
  let entering = false;
  function next() {
    if (t < T.settle) { t = T.settle; nibbled = new Set(['land', T.nibble1, T.nibble2]); splashed = true; return; }
    if (entering) return;
    entering = true;
    void navigate('/play');
  }
  stage.addEventListener('click', next, { signal });
  addEventListener('keydown', (e) => {
    if (e.repeat || e.ctrlKey || e.metaKey || e.altKey || e.code === 'Tab' || e.code.startsWith('Shift')) return; // Tab은 메뉴 이동에 쓴다
    if (e.code === 'Space' || e.code === 'Enter') e.preventDefault();
    next();
  }, { signal });
  signal.addEventListener('abort', () => cancelAnimationFrame(raf), { once: true });

  ready.then(() => { if (signal.aborted) return; fit(); restart(); cancelAnimationFrame(raf); raf = requestAnimationFrame(frame); });
}

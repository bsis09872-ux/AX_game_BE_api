// 낚시터 화면 (templates/game/play.html). Phaser 4로 그린다.
// 장면(Scene) 하나가 preload(그림 읽기) → create(맵·캐릭터 만들기) → update(매 프레임)로 돈다.
// Phaser가 맡는 것: 그림 읽기, 타일맵 그리기, 앞뒤 순서(depth), 카메라 확대, 효과(파티클·흔들기·트윈).
// 직접 하는 것: 픽셀 단위 충돌, HTML로 띄우는 안내문·결과 창·웹 창, 낚시 상태 흐름, WebSocket 멀티플레이, HTTP API.
//
// 팀 공통 화면 규칙(docs/project-structure.md)에 맞춘 점
// - 페이지 HTML의 스크립트는 부분 전환 때 다시 실행되지 않으므로, 동작은 initPlayPage로 pages.js에 "play"로 등록한다
// - 화면을 떠나면(signal) 게임·연결·키 입력·타이머를 모두 정리한다
// - 로그인은 HttpOnly 쿠키다. 토큰을 JavaScript에 저장하지 않고, fetch·WebSocket에 쿠키가 자동으로 붙는다
// - 낚시는 POST /v1/fishing-results, 골드는 GET /v1/wallets/me (팀 API를 그대로 쓴다)

const PHASER_SRC = '/static/vendor/phaser/phaser.min.js';
let phaserLoading = null;
// Phaser는 낚시터에서만 쓰므로 처음 들어올 때 한 번만 읽는다 (다른 화면을 느리게 하지 않게)
function loadPhaser() {
  if (window.Phaser) return Promise.resolve();
  phaserLoading ??= new Promise((ok, fail) => {
    const s = document.createElement('script');
    s.src = PHASER_SRC;
    s.onload = () => ok();
    s.onerror = () => { phaserLoading = null; fail(new Error('Phaser를 읽지 못했어요')); };
    document.head.appendChild(s);
  });
  return phaserLoading;
}

// 그림 주소: 아이템은 팀 규칙 자리(/static/sprites/item_*.png), 캐릭터·UI는 폴더를 나눴다
const spriteUrl = (key) =>
  key.startsWith('char_') ? `/static/sprites/characters/${key}.png`
  : key.startsWith('ui_') ? `/static/sprites/ui/${key}.png`
  : `/static/sprites/${key}.png`;
const itemIconUrl = (icon) => `/static/sprites/item_${icon}.png`;
const ITEM_FALLBACK = 'item_gift_box'; // 그림이 없는 아이템은 선물상자로 보여 준다 (인벤토리 화면과 같은 규칙)

// 팀 API 호출. 오류는 {"detail": {"code", "message"}} 모양이다.
// 401이면 refresh 쿠키로 세션을 한 번 새로 고친 뒤 다시 시도하고, 그래도 안 되면 로그인 화면으로 보낸다
class ApiError extends Error {
  constructor(status, code, message, retryAfter) {
    super(message);
    this.status = status;
    this.code = code;
    this.retryAfter = retryAfter;
  }
}
async function refreshSession() {
  try {
    const r = await fetch('/session/refresh', { method: 'POST', credentials: 'same-origin', cache: 'no-store' });
    return r.ok;
  } catch (e) {
    return false;
  }
}
async function api(path, { method = 'GET', signal } = {}, retried = false) {
  const r = await fetch(path, { method, signal, credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } });
  if (r.status === 401 && !retried && await refreshSession()) return api(path, { method, signal }, true);
  if (r.status === 401) {
    location.assign('/login');
    throw new ApiError(401, 'UNAUTHORIZED', '로그인이 필요해요');
  }
  const body = await r.json().catch(() => null);
  if (!r.ok) {
    const d = body?.detail;
    const message = typeof d?.message === 'string' ? d.message : typeof d === 'string' ? d : `요청이 실패했어요 (${r.status})`;
    throw new ApiError(r.status, d?.code, message, Number(r.headers.get('Retry-After')) || 10);
  }
  return body;
}

export function initPlayPage({ root, signal, navigate }) {
  const gameEl = root.querySelector('#game');
  if (!gameEl) return;
  const $ = (id) => root.querySelector('#' + id);
  const timers = new Set(); // 화면을 떠날 때 지울 setTimeout들
  const on = (target, type, fn, opts = {}) => target.addEventListener(type, fn, { ...opts, signal }); // 떠나면 저절로 풀린다

  // ---------- 화면: 확대 배율(캐릭터 크기)은 고정하고, 창이 커지면 맵을 더 넓게 보여준다 (레벨 맞추기) ----------
  // Phaser 캔버스는 확대한 화면 크기(VW×SCALE)로 만들고, 카메라 zoom으로 SCALE배 키워 그린다. pixelArt: true라 흐려지지 않는다.
  // 원본 크기로 그린 뒤 캔버스를 늘리면 한 번에 SCALE픽셀씩 뚝뚝 움직여서, 화면 1픽셀 단위로 움직이게 이렇게 한다
  const T = 16;
  const ZOOM = 3;         // 정수배 확대. 창이 10칸도 못 보여줄 만큼 좁을 때만 2배로 줄인다
  let W = 320, H = 192;   // 맵 전체 크기(px). 맵 파일을 읽은 뒤 정해진다
  let VW = 320, VH = 192; // 화면에 보이는 크기(px). 창 크기로 정해지고, 맵보다 크지는 않다
  const DEBUG = new URLSearchParams(location.search).has('debug'); // ?debug: 발 상자와 막힌 픽셀을 그린다
  let game = null; // Phaser.Game. 맵 파일을 읽어 크기를 안 뒤에 만든다
  function fit() {
    // 가로: 페이지 폭, 세로: 창 높이에서 상단 메뉴와 아래 안내문 자리를 뺀 만큼
    const top = gameEl.getBoundingClientRect().top + scrollY;
    const pad = getComputedStyle(gameEl.parentElement); // clientWidth에는 안쪽 여백이 들어 있어서 빼야 가로로 넘치지 않는다
    const availW = gameEl.parentElement.clientWidth - parseFloat(pad.paddingLeft) - parseFloat(pad.paddingRight) - 6;
    const availH = innerHeight - top - 50;
    const scale = availW >= 10 * T * ZOOM ? ZOOM : 2;
    VW = Math.max(T, Math.min(W, Math.floor(availW / scale)));
    VH = Math.max(T, Math.min(H, Math.floor(availH / scale)));
    gameEl.style.width = VW * scale + 6 + 'px';
    if (game) game.scale.resize(VW * scale, VH * scale);
    scene?.cameras.main.setZoom(scale);
    return scale;
  }
  let SCALE = 2; // fit()이 정한다
  // 위치를 화면 픽셀 칸에 맞춘다 (맵 1픽셀 = 화면 SCALE픽셀이라, 1/SCALE 단위로 반올림)
  const snap = (v) => Math.round(v * SCALE) / SCALE;

  // ---------- 맵: Tiled로 그린 파일을 읽는다 (static/maps/world.tmj, /play?map=lake 이면 lake.tmj) ----------
  // 그리기는 Phaser 타일맵이 하고, 여기서는 파일을 확인한 뒤 낚시·충돌·앞뒤 순서에 쓸 정보를 정리한다.
  // 타일 속성 solid = 지나갈 수 없음, water = 물(낚시하는 곳, 지나갈 수 없음)
  // 오브젝트: 이름 spawn = 시작 위치(발밑), 클래스 auction = 근처에서 스페이스·클릭하면 경매장이 열리는 곳
  const MAP_NAME = gameEl.dataset.map; // 서버(/play?map=)가 형식을 확인해 넣어 준다
  const MAP_URL = `/static/maps/${/^[\w-]+$/.test(MAP_NAME || '') ? MAP_NAME : 'world'}.tmj`;
  const GID_MASK = 0x1fffffff; // 타일 뒤집기 표시 비트는 무시한다
  const map = { data: null, cols: 0, rows: 0, layers: [], standing: [], block: new Uint8Array(0), tilesets: [], objects: [], solid: [], water: [], innerWater: [], auctionAreas: [] };
  // 캐릭터 그림의 왼쪽 위. face: 1 오른쪽, -1 왼쪽 / dir: 'down' | 'up' | 'side' / walked: 지금까지 걸은 거리(통통 모션 박자)
  const PLAYER = { x: 0, y: 0, face: 1, dir: 'down', walked: 0 };
  // 고를 수 있는 캐릭터. 이름은 서버(game/domain/player.py의 SKINS)와 같다.
  // 캐릭터마다 앞모습(char_X)·뒷모습(char_X_up)·오른쪽 옆모습(char_X_side) 그림이 있고, 왼쪽은 옆모습을 뒤집어 쓴다 (낚시꾼은 char_player)
  const SKINS = { angler: '낚시꾼', girl: '소녀', boy: '소년', ghost: '유령', ranger: '초록 망토', knight: '기사' };
  const DIRS = ['down', 'up', 'side'];
  const skinSprite = (skin, dir = 'down') => {
    const base = skin === 'angler' || !SKINS[skin] ? 'char_player' : 'char_' + skin;
    return dir === 'down' || !DIRS.includes(dir) ? base : `${base}_${dir}`;
  };
  let mySkin = (() => { try { const s = localStorage.getItem('fa.skin'); return SKINS[s] ? s : 'angler'; } catch (e) { return 'angler'; } })();
  // 낚시꾼 그림을 고른 캐릭터·보는 방향에 맞춘다 (옆모습만 face로 좌우를 뒤집는다). 나와 다른 사람이 같이 쓴다
  const placeAngler = (image, dir, face, x, y, skin) =>
    place(image.setTexture(skinSprite(skin || 'angler', dir)), x, y, dir === 'side' && face < 0);
  // 발밑 상자(10×6)로만 충돌을 잰다. 머리는 나무·지붕과 겹쳐도 된다.
  const FOOT = { x: 3, y: 10, w: 10, h: 6 };

  async function getJSON(url) {
    const r = await fetch(url, { cache: 'no-cache', signal });
    if (!r.ok) throw new Error(`${url}을 읽지 못했어요 (${r.status})`);
    return r.json();
  }
  const resolve = (path, base) => new URL(path, location.origin + base).pathname;
  function tileOf(gid) {
    gid &= GID_MASK;
    if (!gid) return null;
    const ts = map.tilesets.find((t) => gid >= t.firstgid);
    const id = gid - ts.firstgid;
    return { ts, id, props: ts.props[id] || {} };
  }
  const objRect = (o) => (o.gid ? { x: o.x, y: o.y - o.height, w: o.width, h: o.height } : { x: o.x, y: o.y, w: o.width, h: o.height });

  async function loadMap() {
    const data = await getJSON(MAP_URL);
    if (data.infinite) throw new Error('무한 맵은 못 읽어요. Tiled 맵 속성에서 Infinite를 꺼 주세요');
    if (data.tilewidth !== T || data.tileheight !== T) throw new Error('타일 크기는 16×16이어야 해요');
    map.cols = data.width; map.rows = data.height;
    W = map.cols * T; H = map.rows * T;
    for (const [i, ts] of data.tilesets.entries()) {
      let def = ts, base = MAP_URL;
      if (ts.source) { // 맵 밖에 따로 저장한 타일셋은 JSON(.tsj)만 읽는다
        if (!/\.(tsj|json)$/.test(ts.source)) throw new Error(`타일셋 ${ts.source}: .tsj로 저장하거나 맵에 포함(Embed)해 주세요`);
        base = resolve(ts.source, MAP_URL);
        def = await getJSON(base);
        data.tilesets[i] = { ...def, firstgid: ts.firstgid }; // Phaser는 맵 밖 타일셋을 못 읽으므로 맵 안에 넣어 준다
      }
      const props = {};
      (def.tiles || []).forEach((t) => { props[t.id] = Object.fromEntries((t.properties || []).map((p) => [p.name, p.value])); });
      map.tilesets.push({
        name: def.name, key: 'tiles_' + def.name, url: resolve(def.image, base), margin: def.margin || 0, spacing: def.spacing || 0,
        firstgid: ts.firstgid, props,
      });
    }
    map.tilesets.sort((a, b) => b.firstgid - a.firstgid); // firstgid가 큰 것부터 찾는다
    (function walk(layers) {
      for (const l of layers) {
        if (l.visible === false) continue;
        if (l.type === 'group') walk(l.layers);
        else if (l.type === 'tilelayer') {
          if (!Array.isArray(l.data)) throw new Error(`레이어 ${l.name}: Tiled 맵 속성에서 타일 레이어 형식을 CSV로 바꿔 주세요`);
          map.layers.push(l.data);
        } else if (l.type === 'objectgroup') map.objects.push(...l.objects.filter((o) => o.visible !== false));
      }
    })(data.layers);

    const grid = () => [...Array(map.rows)].map(() => Array(map.cols).fill(false));
    map.solid = grid(); map.water = grid();
    const mark = (r, c, props) => {
      if (props.water) map.water[r][c] = map.solid[r][c] = true;
      else if (props.solid) map.solid[r][c] = true;
    };
    map.layers.forEach((layer) => layer.forEach((gid, i) => { const t = tileOf(gid); if (t) mark(Math.floor(i / map.cols), i % map.cols, t.props); }));
    let spawn = null;
    for (const o of map.objects) {
      const kind = o.type || o.class || '', rect = objRect(o);
      if (o.name === 'spawn') spawn = { x: o.x, y: o.y };
      if (kind === 'auction') map.auctionAreas.push(rect);
      const t = o.gid && tileOf(o.gid);
      if (t) for (let r = Math.floor(rect.y / T); r <= Math.floor((rect.y + rect.h - 1) / T); r++)
        for (let c = Math.floor(rect.x / T); c <= Math.floor((rect.x + rect.w - 1) / T); c++)
          if (map.solid[r]?.[c] !== undefined) mark(r, c, t.props);
    }
    // 사방이 물인 칸: 찌가 떨어지고 물결이 반짝이는 곳
    const isWater = (r, c) => !!map.water[r]?.[c];
    for (let r = 0; r < map.rows; r++) for (let c = 0; c < map.cols; c++)
      if (isWater(r, c) && isWater(r - 1, c) && isWater(r + 1, c) && isWater(r, c - 1) && isWater(r, c + 1)) map.innerWater.push([c, r]);

    if (!spawn) { // spawn이 없으면 지나갈 수 있는 첫 칸에서 시작한다
      const i = map.solid.flat().findIndex((s) => !s);
      spawn = { x: (i % map.cols) * T + 8, y: Math.floor(i / map.cols) * T + 13 };
    }
    PLAYER.x = spawn.x - FOOT.x - FOOT.w / 2; PLAYER.y = spawn.y - FOOT.y - FOOT.h / 2;
    map.data = data;
    splitStanding();
    SCALE = fit(); // 맵 크기를 알았으니 보이는 범위를 다시 정한다
  }

  // ---------- 앞뒤 순서 ----------
  // 나무·건물처럼 '서 있는 것'은 땅 레이어에서 빼서 따로 그림(Image)으로 세우고, depth를 밑변(y)으로 준다.
  // 캐릭터도 depth를 발밑 y로 주면 Phaser가 depth가 작은 것부터 그려서,
  // 캐릭터가 나무 뒤(위쪽)에 있으면 나무가 캐릭터를 가리고, 앞(아래쪽)에 있으면 캐릭터가 나무를 가린다.
  // 서 있는 것 = 첫 레이어(땅) 말고, 물이 아닌 막힌(solid) 칸이 하나라도 있는 레이어(건물·장식)의 타일.
  // 꽃·눈밭처럼 막힌 칸이 없는 레이어는 땅으로 둔다.
  // 세로로 이어진 타일을 덩어리로 묶고, 덩어리의 맨 아래 칸 아래쪽을 밑변으로 삼는다
  function splitStanding() {
    map.standing = []; // { y: 밑변, tiles: [[레이어 번호, 칸 c, 칸 r, gid]] }
    const isBlock = (gid) => { const p = tileOf(gid)?.props || {}; return p.solid && !p.water; };
    // 물은 늘 땅이다. 물 레이어에 막힌 타일이 섞여 있어도 호수가 통째로 서 있는 것이 되어 찌를 덮지 않게 빈칸처럼 건너뛴다
    const isWater = (gid) => !!tileOf(gid)?.props.water;
    map.layers.forEach((layer, li) => {
      if (li === 0 || !layer.some(isBlock)) return;
      const at = (r, c) => layer[r * map.cols + c] & GID_MASK;
      const piece = (c, from, to) => { // from~to 행을 한 덩어리로 묶는다
        const tiles = [];
        for (let k = from; k <= to; k++) tiles.push([li, c, k, at(k, c)]);
        map.standing.push({ y: (to + 1) * T, tiles });
      };
      // 위에서부터 내려가며 막힌 칸을 만날 때마다 덩어리를 끊는다.
      // 나무 꼭대기(지나갈 수 있음)는 아래 줄기(막힘)와 한 덩어리가 되고, 선물상자 바로 아래 빼빼로는 따로 덩어리가 된다
      for (let c = 0; c < map.cols; c++) {
        let top = -1;
        for (let r = 0; r <= map.rows; r++) {
          const gid = r < map.rows ? at(r, c) : 0;
          if (!gid || isWater(gid)) { if (top >= 0) piece(c, top, r - 1); top = -1; continue; }
          if (top < 0) top = r;
          if (isBlock(gid)) { piece(c, top, r); top = -1; }
        }
      }
    });
  }
  // 캐릭터의 밑변 = 발밑 상자의 아래쪽. 같은 밑변이면 캐릭터가 앞에 보이게 0.5를 더한다
  const feetDepth = (y) => y + FOOT.y + FOOT.h + 0.5;

  // ---------- 충돌: 픽셀 단위 ----------
  // 막힌(solid) 타일은 칸 전체가 아니라 그림이 그려진 픽셀만 막는다. 그래서 빼빼로처럼 가는 것 사이의 틈새로 지나갈 수 있다.
  // 물(water)은 낚시 자리를 칸 단위로 정하므로 칸 전체를 막는다.
  // Phaser Arcade Physics는 타일을 칸 단위로만 막으므로 쓰지 않고, 발 상자 안 픽셀을 직접 검사한다.
  // 타일셋 픽셀은 Phaser가 읽어 둔 그림(textures)에서 꺼내므로 그림을 다 읽은 뒤(create) 만든다
  function buildBlock(textures) {
    map.block = new Uint8Array(W * H);
    const cache = new Map(); // 타일셋 그림의 픽셀 (한 번만 읽는다)
    const pixels = (ts) => {
      if (!cache.has(ts)) {
        const src = textures.get(ts.key).getSourceImage();
        const c = document.createElement('canvas');
        c.width = src.width; c.height = src.height;
        const g = c.getContext('2d');
        g.drawImage(src, 0, 0);
        cache.set(ts, g.getImageData(0, 0, c.width, c.height));
      }
      return cache.get(ts);
    };
    const stamp = (gid, x0, y0) => {
      const t = tileOf(gid);
      if (!t || !(t.props.solid || t.props.water)) return;
      const d = pixels(t.ts), cols = Math.floor((d.width - 2 * t.ts.margin + t.ts.spacing) / (T + t.ts.spacing));
      const sx = t.ts.margin + (t.id % cols) * (T + t.ts.spacing), sy = t.ts.margin + Math.floor(t.id / cols) * (T + t.ts.spacing);
      for (let y = 0; y < T; y++) for (let x = 0; x < T; x++) {
        const mx = x0 + x, my = y0 + y;
        if (mx < 0 || my < 0 || mx >= W || my >= H) continue;
        const opaque = d.data[((sy + y) * d.width + sx + x) * 4 + 3] >= 128; // 반투명 그림자는 막지 않는다
        if (t.props.water || opaque) map.block[my * W + mx] = 1;
      }
    };
    map.layers.forEach((layer) => layer.forEach((gid, i) => stamp(gid, (i % map.cols) * T, Math.floor(i / map.cols) * T)));
    map.objects.forEach((o) => { if (o.gid) stamp(o.gid, Math.round(o.x), Math.round(o.y - o.height)); });
  }
  function canStand(x, y) {
    if (x + FOOT.x < 0 || y < 0 || x + FOOT.x + FOOT.w > W || y + FOOT.y + FOOT.h > H) return false;
    // 발밑 상자 안 픽셀 중 하나라도 막혀 있으면 설 수 없다
    const x0 = Math.floor(x + FOOT.x), x1 = Math.floor(x + FOOT.x + FOOT.w - 1);
    const y0 = Math.floor(y + FOOT.y), y1 = Math.floor(y + FOOT.y + FOOT.h - 1);
    for (let py = y0; py <= y1; py++) for (let px = x0; px <= x1; px++) if (map.block[py * W + px]) return false;
    return true;
  }

  const foot = () => ({ x: PLAYER.x + FOOT.x + FOOT.w / 2, y: PLAYER.y + FOOT.y + FOOT.h / 2 });
  // 발밑에서 가장 가까운 물 칸 (3칸 안)
  function nearestWater() {
    const f = foot(), fc = Math.floor(f.x / T), fr = Math.floor(f.y / T);
    let best = null;
    for (let r = fr - 3; r <= fr + 3; r++) for (let c = fc - 3; c <= fc + 3; c++) {
      if (!map.water[r]?.[c]) continue;
      const dx = Math.max(c * T - f.x, 0, f.x - (c + 1) * T), dy = Math.max(r * T - f.y, 0, f.y - (r + 1) * T);
      const d = Math.hypot(dx, dy);
      if (!best || d < best.d) best = { d, x: c * T + 8, y: r * T + 8 };
    }
    return best;
  }
  const nearLake = () => (nearestWater()?.d ?? 99) <= 10;
  function inAuctionArea(x, y, margin) {
    return map.auctionAreas.some((a) => x >= a.x - margin && x <= a.x + a.w + margin && y >= a.y - margin && y <= a.y + a.h + margin);
  }
  const atAuction = () => { const f = foot(); return inAuctionArea(f.x, f.y, 10); };

  // ---------- 낚시 상태 ----------
  // idle → rodOut → casting → waiting → bite → reeling → caught / missed
  // 게임 시계: 프레임 사이 간격을 최대 100ms로 잘라 더한다. 창이 가려져 갱신이 멈추면 게임 시간도 멈춘다.
  let clock = 0;
  let state = 'idle', since = 0, bobber = null, biteAt = 0, caught = null, busy = false, msg = '';
  const REEL_MS = 700; // 찌를 머리 위까지 끌어올리는 시간
  let reelAt = null; // 끌어올리는 중인 찌(또는 잡은 물건)의 지금 위치
  let note = '', noteUntil = 0; // 잠깐 띄우는 안내 문구
  // 서버가 429로 알려 준 쿨다운이 끝나는 실제 시각(ms). 창이 가려져도 줄어야 하므로 게임 시계가 아닌 Date.now()로 잰다
  let cooldownUntil = 0;
  const cooldownLeft = () => Math.max(0, Math.ceil((cooldownUntil - Date.now()) / 1000));
  const prompt = $('prompt');
  const setState = (s, m = '') => { state = s; since = clock; msg = m; };
  const flash = (text) => { note = text; noteUntil = clock + 1500; };
  // 웹 창이 열려 있거나 열리는 중(화면 전환)이면 게임 입력을 막는다
  const overlayOpen = () => wipe.target === 1 || !$('overlay').classList.contains('hidden');
  // 낚싯대 끝: 손에 쥔 낚싯대(아래 그리기)의 끝 픽셀
  const rodTip = () => ({ x: snap(PLAYER.x) + (PLAYER.face > 0 ? 23 : -8), y: snap(PLAYER.y) + 2 });

  function promptText() {
    if (state === 'idle') {
      if (clock < noteUntil) return note;
      if (atAuction()) return '스페이스: 경매장 들어가기';
      return nearLake() ? '클릭·스페이스: 낚싯대 꺼내기' : 'WASD로 이동 · 호숫가에서 낚시';
    }
    const left = cooldownLeft();
    if (left && (state === 'missed' || state === 'rodOut')) return `물고기가 다 도망갔어요. ${left}초 뒤에 다시 던져 보세요`;
    return {
      rodOut: '클릭: 찌 던지기',
      casting: '휘익—',
      waiting: '입질을 기다리는 중… (느낌표가 뜨면 클릭!)',
      bite: '지금 클릭!',
      reeling: '끌어올리는 중…',
      caught: '낚았다!',
      missed: msg || '놓쳤어요… 클릭해서 다시 던지기',
    }[state];
  }

  function act() {
    if (busy || overlayOpen()) return;
    if (state === 'idle') {
      if (atAuction()) return openWin('/auction');
      if (!nearLake()) return flash('호숫가로 가야 낚시할 수 있어요');
      return setState('rodOut'); // 마지막으로 본 방향 그대로 낚싯대를 꺼낸다
    }
    if (state === 'rodOut' || state === 'missed') {
      if (cooldownLeft()) return; // 카운트다운이 끝나야 다시 던진다
      bobber = castTarget();
      return setState('casting');
    }
    if (state === 'waiting') { bobber = null; return setState('missed', '너무 일찍 당겼어요! 클릭해서 다시 던지기'); }
    if (state === 'bite') return reel();
  }

  // 찌는 발밑에서 1.5~4칸 떨어진, 사방이 물인 칸 중 하나에 떨어진다. 보는 쪽 칸을 먼저 고르고,
  // 보는 쪽에 없으면 아무 쪽이나, 그것도 없으면 가장 가까운 물 칸
  function castTarget() {
    const f = foot();
    const pool = map.innerWater.map(([c, r]) => ({ x: c * T + 8, y: r * T + 8 }));
    const ring = pool.filter((p) => { const d = Math.hypot(p.x - f.x, p.y - f.y); return d >= 24 && d <= 64; });
    const ahead = ring.filter((p) => (PLAYER.dir === 'up' ? p.y < f.y - 4 : PLAYER.dir === 'down' ? p.y > f.y + 4 : (p.x - f.x) * PLAYER.face > 4));
    const pick = ahead.length ? ahead : ring;
    const p = pick.length ? pick[Math.floor(Math.random() * pick.length)] : nearestWater();
    return { x: Math.round(p.x + (Math.random() - 0.5) * 8 - 8), y: Math.round(p.y + (Math.random() - 0.5) * 8 - 9) }; // 찌 그림의 왼쪽 위
  }

  // ---------- 이동 (WASD·방향키) ----------
  const MOVE_KEYS = { KeyW: [0, -1], KeyS: [0, 1], KeyA: [-1, 0], KeyD: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] };
  const SPEED = 60; // 원본 해상도 기준 초당 픽셀 (약 4칸). 서버(world/domain/player.py)의 WALK_SPEED와 같다
  const keys = new Set();
  let walking = false;
  function move(dt) {
    let dx = 0, dy = 0;
    keys.forEach((k) => { dx += MOVE_KEYS[k][0]; dy += MOVE_KEYS[k][1]; });
    walking = false;
    if ((!dx && !dy) || busy || state === 'reeling' || state === 'caught' || overlayOpen()) return;
    if (state !== 'idle') { // 낚시 중에 움직이면 낚싯대를 거둔다
      if (state !== 'rodOut' && state !== 'missed') flash('낚싯대를 거뒀어요');
      bobber = null;
      setState('idle');
    }
    if (dx) PLAYER.face = dx > 0 ? 1 : -1;
    PLAYER.dir = dx ? 'side' : dy < 0 ? 'up' : 'down'; // 대각선은 옆모습
    const len = Math.hypot(dx, dy), step = (SPEED * dt) / 1000;
    const nx = PLAYER.x + (dx / len) * step, ny = PLAYER.y + (dy / len) * step;
    const ox = PLAYER.x, oy = PLAYER.y;
    if (canStand(nx, PLAYER.y)) PLAYER.x = nx; // 축마다 따로 막아서 벽을 따라 미끄러진다
    if (canStand(PLAYER.x, ny)) PLAYER.y = ny;
    PLAYER.walked += Math.hypot(PLAYER.x - ox, PLAYER.y - oy);
    walking = true;
  }

  // ---------- 멀티플레이 (WebSocket /v1/ws/world) ----------
  // 내 위치는 바뀌었을 때만 최대 0.1초에 한 번 보낸다(멈추면 마지막 위치 한 번).
  // 다른 사람은 받은 위치 두 개 사이를 0.15초 늦게 이어 그린다(보간). 돈·아이템은 계속 HTTP API로 한다.
  const MAP_KEY = MAP_URL.match(/([\w-]+)\.tmj$/)[1]; // 같은 맵에 있는 사람끼리만 보인다
  // 디싱크 실험: 주소에 ?lag=300&jitter=200&drop=0.3&nointerp 를 붙이면 받은 소식을 일부러 늦게·뒤섞어·빠뜨려 처리한다.
  // 아무것도 안 붙이면 평소와 똑같다. lag·jitter는 ms, drop은 위치 소식(state)을 버릴 비율(0~1), nointerp는 보간을 끈다
  const LABQ = new URLSearchParams(location.search);
  const LAB = { lag: +LABQ.get('lag') || 0, jitter: +LABQ.get('jitter') || 0, drop: Math.min(1, +LABQ.get('drop') || 0), nointerp: LABQ.has('nointerp') };
  const LAB_TEXT = [LAB.lag && `지연 ${LAB.lag}ms`, LAB.jitter && `흔들림 ${LAB.jitter}ms`, LAB.drop && `손실 ${Math.round(LAB.drop * 100)}%`, LAB.nointerp && '보간 끔'].filter(Boolean).join(' · ');
  const SEND_EVERY = 100, INTERP_DELAY = LAB.nointerp ? 0 : 150, PING_EVERY = 10000, SILENT_LIMIT = 25000;
  const NET = { ws: null, open: false, stopped: false, retry: 0, seq: 0, lastSent: 0, lastKey: '', lastHeard: 0, pingMs: null };
  const others = new Map(); // id → { nickname, buf: [{ t, x, y, face, dir, pose, bobber }], label, body, rod, bob, at, wasBobber }
  const netEl = $('net'), namesEl = $('names');

  function showNet(text) {
    netEl.classList.toggle('on', NET.open);
    netEl.textContent = (text ?? `${others.size + 1}명${NET.pingMs != null ? ` · ${NET.pingMs}ms` : ''}`) + (LAB_TEXT ? ` · 🧪 ${LAB_TEXT}` : '');
  }
  function addOther(p) {
    removeOther(p.id);
    const label = document.createElement('div');
    label.textContent = p.nickname;
    namesEl.appendChild(label);
    // depth는 그릴 때마다 발밑 y로 맞춘다 (drawOthers)
    const img = (key) => scene.add.image(0, 0, key).setOrigin(0).setVisible(false);
    others.set(p.id, { nickname: p.nickname, buf: [], label, body: img('char_player'), rod: img('ui_rod'), bob: img('ui_bobber'), line: scene.add.graphics(), at: null, wasBobber: false });
    pushSample(p);
  }
  function removeOther(id) {
    const o = others.get(id);
    if (!o) return;
    o.label.remove();
    o.body.destroy(); o.rod.destroy(); o.bob.destroy(); o.line.destroy();
    others.delete(id);
  }
  function pushSample(p) {
    const o = others.get(p.id);
    if (!o) return;
    o.buf.push({ t: performance.now(), x: p.x, y: p.y, face: p.face, dir: p.dir, pose: p.pose, bobber: p.bobber, skin: p.skin });
    if (o.buf.length > 20) o.buf.shift();
  }
  // 보간: 지금보다 INTERP_DELAY 전 시각이 받은 위치 a와 b 사이 어디쯤인지 계산한다
  function sampleAt(buf, t) {
    while (buf.length > 2 && buf[1].t <= t) buf.shift();
    const a = buf[0], b = buf[1];
    if (!b || t <= a.t) return a;
    const k = Math.min(1, (t - a.t) / (b.t - a.t));
    const d = k < 1 ? a : b; // 방향·동작·찌는 섞을 수 없으니 가까운 쪽 것을 쓴다
    return { ...d, x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k };
  }

  function connect() {
    if (NET.stopped || signal.aborted) return;
    // 로그인은 쿠키(access_token)가 연결 요청에 자동으로 붙는다. 맵과 캐릭터는 비밀이 아니라서 주소로 보낸다
    const query = new URLSearchParams({ map: MAP_KEY, skin: mySkin });
    const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/v1/ws/world?${query}`);
    NET.ws = ws;
    showNet('연결 중…');
    ws.onopen = () => { NET.lastHeard = Date.now(); };
    ws.onmessage = (e) => {
      NET.lastHeard = Date.now();
      const m = JSON.parse(e.data);
      if (LAB.drop && m.type === 'state' && Math.random() < LAB.drop) return; // 실험: 위치 소식을 일부러 버린다
      const delay = LAB.lag + Math.random() * LAB.jitter; // 실험: 늦게 처리한다. 흔들림이 있으면 순서까지 뒤섞인다
      if (delay) setTimeout(() => handle(m), delay);
      else handle(m);
    };
    function handle(m) {
      if (NET.ws !== ws) return; // 늦게 처리하는 사이에 연결이 바뀌었으면 버린다
      if (m.type === 'welcome') {
        NET.open = true; NET.retry = 0; NET.lastKey = ''; // 다시 들어왔으면 내 위치를 곧바로 다시 알린다
        others.forEach((_, id) => removeOther(id));
        m.players.forEach(addOther);
        sendPing();
      } else if (m.type === 'join') addOther(m.player);
      else if (m.type === 'leave') removeOther(m.id);
      else if (m.type === 'state') m.players.forEach(pushSample);
      else if (m.type === 'correct') { PLAYER.x = m.x; PLAYER.y = m.y; NET.lastKey = ''; } // 서버가 순간이동을 막았다
      else if (m.type === 'pong') NET.pingMs = Math.round(performance.now() - m.t);
      else if (m.type === 'error') console.warn('멀티플레이:', m.detail.code, m.detail.message);
      if (NET.open) showNet();
    }
    ws.onclose = (e) => {
      if (NET.ws !== ws) return;
      NET.open = false; NET.ws = null;
      others.forEach((_, id) => removeOther(id));
      if (NET.stopped || signal.aborted) return; // 화면을 떠나며 직접 닫았다
      if (e.code === 4401) { // 세션 만료: refresh 쿠키로 새로 고쳐 다시 붙고, 안 되면 로그인 화면으로
        refreshSession().then((ok) => (ok ? connect() : location.assign('/login')));
        return;
      }
      if (e.code === 4409) { NET.stopped = true; return showNet('다른 곳에서 접속해서 끊겼어요'); }
      if (e.code === 4403 || e.code === 1008 || e.code === 1009) { NET.stopped = true; return showNet('연결이 끊겼어요 (새로고침)'); }
      // 1초, 2초, 4초 … 최대 30초. 서버가 다시 켜질 때 모두 한꺼번에 몰리지 않게 조금씩 흔든다
      const wait = Math.min(30000, 1000 * 2 ** NET.retry++) * (0.8 + Math.random() * 0.4);
      showNet(`다시 연결 중… (${Math.ceil(wait / 1000)}초)`);
      timers.add(setTimeout(connect, wait));
    };
  }
  function sendPing() {
    if (NET.open) NET.ws.send(JSON.stringify({ type: 'ping', t: Math.round(performance.now()) }));
  }
  // 와이파이가 끊기면 브라우저가 늦게 알아챈다. 10초마다 ping, 25초 동안 아무 소식이 없으면 직접 끊고 재연결한다
  const pingTimer = setInterval(() => {
    if (!NET.ws || NET.ws.readyState !== WebSocket.OPEN) return;
    if (Date.now() - NET.lastHeard > SILENT_LIMIT) return NET.ws.close();
    sendPing();
  }, PING_EVERY);

  function sendMove(t) {
    if (!NET.open || t - NET.lastSent < SEND_EVERY) return;
    const showBobber = bobber && (state === 'waiting' || state === 'bite' || state === 'reeling');
    const me = {
      x: Math.round(PLAYER.x), y: Math.round(PLAYER.y), face: PLAYER.face, dir: PLAYER.dir,
      pose: state === 'idle' ? (walking ? 'walk' : 'idle') : 'rod',
      bobber: showBobber ? (state === 'reeling' && reelAt ? [reelAt.x, reelAt.y] : [bobber.x, bobber.y]) : null, // 끌어올리는 중이면 지금 위치
    };
    const key = JSON.stringify(me);
    if (key === NET.lastKey) return; // 가만히 있으면 아무것도 안 보낸다
    NET.lastKey = key; NET.lastSent = t;
    NET.ws.send(JSON.stringify({ type: 'move', seq: ++NET.seq, ...me }));
  }

  function drawOthers(now) {
    const at = performance.now() - INTERP_DELAY;
    others.forEach((o) => {
      if (!o.buf.length) return;
      o.line.clear().lineStyle(1, 0x3f2631);
      const p = sampleAt(o.buf, at), px = snap(p.x), py = snap(p.y), depth = feetDepth(py);
      placeAngler(o.body.setDepth(depth), p.dir, p.face, px, py - (p.pose === 'walk' && Math.floor(now / 120) % 2 ? 1 : 0), p.skin);
      o.rod.setVisible(p.pose === 'rod');
      if (p.pose === 'rod') place(o.rod.setDepth(depth + 0.1), px + (p.face > 0 ? 10 : -10), py, p.face < 0);
      o.bob.setVisible(!!p.bobber);
      if (p.bobber) {
        const [bx, by] = p.bobber, bob = Math.sin(now / 220) > 0 ? 1 : 0;
        line(o.line.setDepth(depth + 0.2), { x: px + (p.face > 0 ? 23 : -8), y: py + 2 }, { x: bx + 8, y: by + 6 + bob });
        place(o.bob.setDepth(depth + 0.3), bx, by - 3 + bob);
        if (!o.wasBobber) splash(bx + 8, by + 6, 6); // 다른 사람 찌가 물에 떨어졌다
      }
      o.wasBobber = !!p.bobber;
      o.at = { x: px, y: py };
    });
  }
  // 닉네임은 글자가 흐려지지 않게 캔버스 위 HTML로 띄운다. 카메라 위치가 정해진 뒤(render)에 맞춘다
  function placeLabels() {
    const view = scene.cameras.main.worldView, cx = view.x, cy = view.y;
    others.forEach((o) => {
      if (!o.at) return;
      const sx = (o.at.x + 8 - cx) * SCALE, sy = (o.at.y - 1 - cy) * SCALE;
      const visible = sx > -40 && sx < VW * SCALE + 40 && sy > 0 && sy < VH * SCALE + 20;
      o.label.style.display = visible ? '' : 'none';
      if (visible) { o.label.style.left = sx + 'px'; o.label.style.top = sy + 'px'; }
    });
  }

  // 끌어올리는 화면은 draw가 바로 시작하고, 여기서는 서버 결과만 받아 caught에 넣는다.
  // 실패하면 끌어올리던 찌를 거두고 missed로 바꾼다
  async function reel() {
    busy = true;
    reelAt = null;
    if (bobber) splash(bobber.x + 8, bobber.y + 6, 10); // 찌가 물에서 빠져나온다
    setState('reeling');
    try {
      // 낚시 결과는 서버(인벤토리)가 정한다. 응답 = {id, definition: {name, category, icon, …}, status, origin, …}
      // 그림까지 다 읽은 뒤에 caught에 넣는다. 먼저 넣으면 아직 없는 그림을 그리려 한다
      const item = await api('/v1/fishing-results', { method: 'POST', signal });
      const d = item.definition;
      caught = { id: item.id, name: d.name, category: d.category, icon: d.icon, key: await itemTexture(d.icon) };
    } catch (e) {
      if (signal.aborted) return;
      caught = null;
      bobber = null;
      if (e.status === 429) { // FISHING_COOLDOWN. Retry-After = 남은 초
        cooldownUntil = Date.now() + e.retryAfter * 1000;
        setState('missed', '이제 다시 던질 수 있어요! 클릭해서 던지기');
      } else if (e.status === 404) setState('missed', '지금은 낚시를 할 수 없어요 (클릭해서 다시)');
      else setState('missed', e.message + ' (클릭해서 다시)');
    }
    busy = false;
  }
  // 잡은 물건 그림은 그때그때 Phaser 로더로 읽는다. 못 읽으면 기본 그림(선물상자)을 쓴다
  function itemTexture(icon) {
    const key = 'item_' + icon;
    if (scene.textures.exists(key)) return Promise.resolve(key);
    return new Promise((ok) => {
      scene.load.image(key, itemIconUrl(icon));
      scene.load.once('complete', () => ok(scene.textures.exists(key) ? key : ITEM_FALLBACK));
      scene.load.start();
    });
  }

  // 화면 위 골드 = 지갑의 사용 가능 금액 (예약금을 뺀 값)
  async function refreshGold() {
    try {
      const wallet = await api('/v1/wallets/me', { signal });
      root.querySelectorAll('[data-gold]').forEach((el) => { el.textContent = wallet.available_balance.toLocaleString(); });
    } catch (e) {
      if (!signal.aborted) console.warn('골드를 불러오지 못했어요:', e.message);
    }
  }

  function showCatch() {
    const icon = document.createElement('img');
    icon.className = 'px s6';
    icon.alt = '';
    icon.src = itemIconUrl(caught.icon);
    icon.onerror = () => { icon.onerror = null; icon.src = spriteUrl(ITEM_FALLBACK); };
    $('catch-slot').replaceChildren(icon);
    $('catch-name').textContent = caught.name;
    $('catch-cat').textContent = `${caught.category} · #${caught.id}`;
    $('catch').classList.remove('hidden');
    refreshGold();
  }
  $('again').addEventListener('click', (e) => {
    e.stopPropagation();
    $('catch').classList.add('hidden');
    caught = null; bobber = null; setState('rodOut');
  }, { signal });

  // ---------- Phaser 장면 ----------
  // 캐릭터마다 앞·뒤·옆 그림을 모두 읽는다 (char_player, char_player_up, char_player_side, char_girl, …)
  const SPRITES = [...Object.keys(SKINS).flatMap((s) => DIRS.map((d) => skinSprite(s, d))),
    'ui_rod', 'ui_bobber', 'ui_exclaim', ITEM_FALLBACK];
  let scene = null; // create()에서 정해진다
  let broken = false; // 그림을 못 읽었으면 장면을 만들지 않는다
  const sp = {}; // 장면에 올린 것들: me, rod, bobber, exclaim, item, line, sparkle, debug
  const fx = {}; // 효과: splash(물보라), shine(반짝이)
  const splash = (x, y, n) => fx.splash?.explode(n, x, y);

  function preload() {
    // 타일셋은 spritesheet(16×16 조각)로 읽는다. 타일맵 그리기에도, 타일 오브젝트(경매사·간판) 그리기에도 쓴다
    for (const ts of map.tilesets) this.load.spritesheet(ts.key, ts.url, { frameWidth: T, frameHeight: T, margin: ts.margin, spacing: ts.spacing });
    for (const k of SPRITES) this.load.image(k, spriteUrl(k));
    this.load.on('loaderror', (file) => {
      if (scene) return; // 게임 중에 읽는 물건 그림은 itemTexture가 기본 그림으로 바꾼다
      broken = true;
      prompt.textContent = `${file.src} 그림을 읽지 못했어요`;
    });
  }

  function create() {
    pageIris(1, 0); // 낚시터에 들어왔다: 화면 가운데에서 원을 연다
    if (broken) return;
    scene = this;
    // 맵 JSON은 loadMap이 이미 읽었으므로 Phaser 캐시에 바로 넣는다
    this.cache.tilemap.add('map', { format: Phaser.Tilemaps.Formats.TILED_JSON, data: map.data });
    const tm = this.make.tilemap({ key: 'map' });
    const tilesets = map.tilesets.map((ts) => tm.addTilesetImage(ts.name, ts.key));
    // 땅 레이어는 depth를 맨 아래(-2)로 둔다. map.layers와 같은 순서(보이는 타일 레이어만)다
    const ground = [];
    tm.layers.forEach((l, i) => { if (l.visible) ground.push(tm.createLayer(i, tilesets).setDepth(-2)); });
    // 서 있는 것은 땅 레이어에서 지우고 칸마다 그림으로 세운다. depth = 덩어리의 밑변 y
    for (const s of map.standing) for (const [li, c, r, gid] of s.tiles) {
      const t = tileOf(gid);
      ground[li].removeTileAt(c, r);
      this.add.image(c * T, r * T, t.ts.key, t.id).setOrigin(0).setDepth(s.y);
    }
    // 맵에 놓은 타일 오브젝트(경매사 등)도 서 있는 것이다. 오브젝트의 y가 곧 밑변이다
    for (const o of map.objects) {
      const t = o.gid && tileOf(o.gid);
      if (t) this.add.image(o.x, o.y - o.height, t.ts.key, t.id).setOrigin(0).setDepth(o.y);
    }
    sp.sparkle = this.add.graphics().setDepth(-1);
    buildBlock(this.textures);

    // 내 캐릭터와 낚시 도구. depth는 draw()에서 발밑 y로 맞춘다
    const img = (key) => this.add.image(0, 0, key).setOrigin(0);
    sp.me = img('char_player');
    sp.rod = img('ui_rod');
    sp.line = this.add.graphics();
    sp.bobber = img('ui_bobber');
    sp.exclaim = img('ui_exclaim');
    sp.item = img(ITEM_FALLBACK).setOrigin(0.5); // 가운데를 기준으로 커졌다 작아진다 (celebrate)
    // 화면 전환 원. 카메라 zoom을 쓰므로 scrollFactor(0)로 고정하면 확대 중심이 어긋난다.
    // 대신 매 프레임 보이는 영역(worldView)의 왼쪽 위로 옮겨서 화면에 붙여 둔다 (drawWipe)
    sp.wipe = this.add.graphics().setDepth(2e6);

    // 효과: 1×1 흰 점 그림을 만들어 파티클로 쓴다. 색은 tint로 입힌다. emitting: false라 explode()할 때만 터진다
    this.make.graphics({}, false).fillStyle(0xffffff).fillRect(0, 0, 1, 1).generateTexture('dot', 1, 1).destroy();
    const burst = (tint, config) => this.add.particles(0, 0, 'dot', { emitting: false, tint, ...config }).setDepth(1e5);
    fx.splash = burst([0xffffff, 0xd9f7ff, 0x9fdcf2], { speed: { min: 20, max: 55 }, angle: { min: 200, max: 340 }, gravityY: 160, lifespan: 550, scale: { start: 2, end: 1 } });
    fx.shine = burst([0xffe27a, 0xffffff, 0xf7b733], { speed: { min: 25, max: 60 }, lifespan: 700, scale: { start: 2, end: 1 }, alpha: { start: 1, end: 0 } });

    if (DEBUG) { // 막힌 픽셀을 빨갛게 덮고, 발 상자를 분홍 테두리로 그린다
      const tex = this.textures.createCanvas('blockmask', W, H), g = tex.getContext(), d = g.createImageData(W, H);
      map.block.forEach((b, i) => { if (b) { d.data[i * 4] = 255; d.data[i * 4 + 3] = 110; } });
      g.putImageData(d, 0, 0);
      tex.refresh();
      this.add.image(0, 0, 'blockmask').setOrigin(0).setDepth(1e6);
      sp.debug = this.add.graphics().setDepth(1e6 + 1);
    }

    // 카메라: SCALE배로 키워 보여 준다. 따라가기는 update에서 followCamera가 직접 한다
    this.cameras.main.setZoom(SCALE);
    if (DEBUG) window.fa = { scene: this, PLAYER }; // ?debug: 콘솔에서 장면·내 위치를 들여다본다

    this.input.on('pointerdown', (pointer) => {
      if (inAuctionArea(pointer.worldX, pointer.worldY, 0)) return openWin('/auction'); // 경매장 건물·경매사를 클릭
      act();
    });
    this.events.on('render', placeLabels);
    connect();
    refreshGold();
  }

  function update(time, delta) {
    if (!sp.me) return;
    const dt = Math.min(delta, 100);
    clock += dt;
    move(dt);
    followCamera();
    draw();
    drawWipe(dt);
  }
  // 카메라는 캐릭터를 그리는 위치(snap한 위치)에서 계산해 발 상자 가운데를 화면 가운데에 둔다. 맵 밖은 보여 주지 않는다.
  // Phaser의 startFollow는 캐릭터와 따로 반올림해서, 둘이 어긋나는 순간마다 캐릭터가 화면에서 앞뒤로 떨렸다.
  // 화면 폭의 절반은 정수로 내린다. 0.5가 섞이면 반올림이 오락가락해서 다시 떨린다
  const camView = { x: 0, y: 0 }; // 보이는 영역의 왼쪽 위 (맵 좌표)
  function followCamera() {
    const cx = snap(PLAYER.x) + FOOT.x + FOOT.w / 2, cy = snap(PLAYER.y) + FOOT.y + FOOT.h / 2;
    camView.x = Math.min(Math.max(snap(cx - Math.floor(VW / 2)), 0), W - VW);
    camView.y = Math.min(Math.max(snap(cy - Math.floor(VH / 2)), 0), H - VH);
    scene.cameras.main.centerOn(camView.x + VW / 2, camView.y + VH / 2);
  }

  // ---------- 그리기: 매 프레임 그림의 위치·모양을 맞춘다 ----------
  const ease = (k) => 1 - Math.pow(1 - k, 2);
  // 그림을 정수 픽셀 위치에 놓는다. flip이면 좌우를 뒤집는다 (왼쪽을 볼 때)
  const place = (image, x, y, flip = false) => image.setPosition(snap(x), snap(y)).setFlipX(flip).setVisible(true);
  function line(g, a, b) {
    const curve = new Phaser.Curves.QuadraticBezier(
      new Phaser.Math.Vector2(a.x + .5, a.y + .5),
      new Phaser.Math.Vector2((a.x + b.x) / 2, Math.max(a.y, b.y) + 6),
      new Phaser.Math.Vector2(b.x + .5, b.y + .5),
    );
    g.strokePoints(curve.getPoints(16));
  }
  // 물결 반짝임 (화면에 보이는 물에서만 고른다)
  function drawSparkles(now) {
    const view = scene.cameras.main.worldView;
    const c0 = Math.floor(view.x / T), c1 = Math.min(map.cols - 1, Math.floor((view.x + VW) / T));
    const r0 = Math.floor(view.y / T), r1 = Math.min(map.rows - 1, Math.floor((view.y + VH) / T));
    sp.sparkle.clear().fillStyle(0xd9f7ff);
    const inner = map.innerWater.filter(([c, r]) => c >= c0 && c <= c1 && r >= r0 && r <= r1);
    for (let i = 0; i < Math.min(9, inner.length); i++) {
      const [c, r] = inner[(i * 37) % inner.length];
      if ((Math.floor(now / 400) + i) % 3) sp.sparkle.fillRect(c * T + ((i * 5 + Math.floor(now / 90)) % 13), r * T + ((i * 3) % 14), 3, 1);
    }
  }

  // 낚았다: 반짝이를 터뜨리고 물건이 크게 튀어 올랐다 줄어든 뒤 결과 창을 띄운다
  function celebrate() {
    fx.shine.explode(20, Math.round(PLAYER.x) + 8, Math.round(PLAYER.y) - 12);
    scene.tweens.add({ targets: sp.item, scale: { from: 2, to: 1 }, duration: 400, ease: 'Back.easeOut' });
    scene.time.delayedCall(350, showCatch);
  }

  function draw() {
    const now = clock;
    const k = now - since;
    drawSparkles(now);
    drawOthers(now);
    sendMove(performance.now());
    const bob = Math.sin(now / 220) > 0 ? 1 : 0;
    const px = snap(PLAYER.x), py = snap(PLAYER.y), depth = feetDepth(py);
    // 통통 모션은 시간이 아니라 걸은 거리에 맞춘다: 8px(반 칸) 걸을 때마다 한 번 들썩인다. 벽에 막혀 제자리면 안 들썩인다
    placeAngler(sp.me.setDepth(depth), PLAYER.dir, PLAYER.face, px, py - (walking && Math.floor(PLAYER.walked / 8) % 2 ? 1 : 0), mySkin);
    sp.rod.setVisible(state !== 'idle').setDepth(depth + 0.1);
    if (state !== 'idle') {
      // 낚싯대: 손잡이를 손(보는 쪽 손) 높이에 맞추고, 꺼내는 동안 아래에서 올라온다
      const lift = state === 'rodOut' ? Math.max(0, 8 - Math.floor(k / 30)) : 0;
      place(sp.rod, px + (PLAYER.face > 0 ? 10 : -10), py + lift, PLAYER.face < 0);
    }
    sp.line.clear().lineStyle(1, 0x3f2631).setDepth(depth + 0.2);
    for (const s of [sp.bobber, sp.exclaim, sp.item]) s.setVisible(false).setDepth(depth + 0.3);
    if (sp.debug) sp.debug.clear().lineStyle(1, 0xff00ff).strokeRect(Math.floor(PLAYER.x) + FOOT.x + .5, Math.floor(PLAYER.y) + FOOT.y + .5, FOOT.w - 1, FOOT.h - 1);
    const tip = rodTip();
    if (state === 'casting' && bobber) {
      const p = Math.min(1, k / 550), x = tip.x + (bobber.x + 8 - tip.x) * ease(p), y = tip.y + (bobber.y + 6 - tip.y) * p - Math.sin(p * Math.PI) * 28;
      line(sp.line, tip, { x, y }); place(sp.bobber, x - 8, y - 9);
      if (p >= 1) { biteAt = now + 2000 + Math.random() * 3000; setState('waiting'); splash(bobber.x + 8, bobber.y + 6, 12); } // 퐁당
    } else if ((state === 'waiting' || state === 'bite') && bobber) {
      const dip = state === 'bite' ? 3 : bob;
      line(sp.line, tip, { x: bobber.x + 8, y: bobber.y + 6 + dip });
      place(sp.bobber, bobber.x, bobber.y - 3 + dip);
      if (state === 'waiting' && now >= biteAt) { // 입질: 찌가 첨벙하고 화면이 살짝 흔들린다
        setState('bite');
        splash(bobber.x + 8, bobber.y + 6, 5);
        scene.cameras.main.shake(160, 0.008);
      }
      if (state === 'bite') {
        const kb = now - since; // 입질이 시작된 뒤 흐른 시간 (이 프레임에서 상태가 바뀌었을 수 있어 다시 잰다)
        const jump = Math.floor(kb / 80) % 2 ? -2 : 0;
        place(sp.exclaim, px, py - 18 + jump);
        if (kb > 1000) { bobber = null; setState('missed', '놓쳤어요… 클릭해서 다시 던지기'); }
      }
    } else if (state === 'reeling' && bobber) {
      // 서버 응답을 기다리지 않고 클릭하자마자 찌를 끌어올린다. 응답이 오면 그 자리부터 잡은 물건을 그린다.
      // 머리 위에 먼저 도착하면 대롱대롱 흔들며 기다리고, 물건이 있으면 결과 창을 띄운다
      const p = Math.min(1, k / REEL_MS);
      const x = bobber.x + (px - bobber.x) * ease(p);
      let y = bobber.y + (py - 20 - bobber.y) * p - Math.sin(p * Math.PI) * 30;
      if (p >= 1 && !caught) y -= Math.sin(now / 90) > 0 ? 1 : 0;
      reelAt = { x: Math.round(x), y: Math.round(y) };
      line(sp.line, tip, { x: reelAt.x + 8, y: reelAt.y + 6 });
      if (caught) place(sp.item.setTexture(caught.key), reelAt.x + 8, reelAt.y + 8);
      else place(sp.bobber, reelAt.x, reelAt.y - 3);
      if (p >= 1 && caught) { setState('caught'); celebrate(); }
    } else if (state === 'caught' && caught) {
      place(sp.item.setTexture(caught.key), px + 8, py - 12 - (Math.floor(now / 300) % 2));
    }
    prompt.textContent = promptText();
  }

  // ---------- 캐릭터 고르기 ----------
  // 고른 캐릭터는 이 브라우저에 기억하고(인증 정보가 아니다), 접속할 때(주소의 skin)와 바꿀 때(skin 메시지) 서버에 알린다
  const skinsEl = $('skins'), skinIcon = $('skin-icon');
  function renderSkins() {
    skinIcon.src = spriteUrl(skinSprite(mySkin));
    skinsEl.innerHTML = Object.entries(SKINS).map(([id, name]) =>
      `<button class="btn${id === mySkin ? ' gold' : ''}" data-skin="${id}"><img class="px s3" src="${spriteUrl(skinSprite(id))}" alt="">${name}</button>`).join('');
  }
  function chooseSkin(skin) {
    mySkin = skin;
    try { localStorage.setItem('fa.skin', skin); } catch (e) { /* 저장이 막혀 있으면 이번 접속에서만 쓴다 */ }
    if (NET.open) NET.ws.send(JSON.stringify({ type: 'skin', skin }));
    renderSkins();
    skinsEl.classList.add('hidden');
  }
  on($('skin-btn'), 'click', (e) => { e.stopPropagation(); skinsEl.classList.toggle('hidden'); });
  on(skinsEl, 'click', (e) => {
    e.stopPropagation();
    const b = e.target.closest('[data-skin]');
    if (b) chooseSkin(b.dataset.skin);
  });
  renderSkins();

  // ---------- 입력 ----------
  // 클릭은 Phaser(pointerdown)가 받고, 키보드는 직접 받는다. Phaser 키보드는 keyCode로 키를 구분하는데
  // 한글 입력 상태에서는 keyCode가 229로 바뀌어 WASD가 안 먹을 수 있다. e.code는 한글 상태에서도 그대로다
  on(window, 'keydown', (e) => {
    if (e.code === 'Escape') { skinsEl.classList.add('hidden'); return closeWin(); }
    if (overlayOpen()) return;
    if (MOVE_KEYS[e.code]) { e.preventDefault(); keys.add(e.code); }
    if (e.code === 'Space') { e.preventDefault(); if (!e.repeat && sp.me) act(); }
  });
  on(window, 'keyup', (e) => keys.delete(e.code));
  on(window, 'blur', () => keys.clear());

  // ---------- 화면 전환: 픽셀 원 ----------
  // 웹 창을 열 때 캐릭터를 가운데로 둔 원이 좁혀지며 화면을 덮고, 다 덮이면 창을 연다. 닫으면 원이 다시 퍼진다.
  // 원 밖을 한 줄(1px)씩 칠한다: 줄마다 원의 왼쪽 끝 바깥과 오른쪽 끝 바깥을 사각형 두 개로 덮는다
  const WIPE = { ms: 700, color: 0x241a1f };
  const wipe = { p: 0, target: 0, done: null }; // p: 0 = 다 걷힘, 1 = 다 덮임
  function wipeTo(target, done) { wipe.target = target; wipe.done = done || null; }
  // 매 프레임: p를 목표 쪽으로 옮기고, 반지름이 (1 - p)만큼 남은 원 바깥을 칠한다 (화면 좌표에 고정)
  function drawWipe(delta) {
    if (wipe.p !== wipe.target) {
      const step = delta / WIPE.ms;
      wipe.p = wipe.target > wipe.p ? Math.min(wipe.target, wipe.p + step) : Math.max(wipe.target, wipe.p - step);
      if (wipe.p === wipe.target && wipe.done) { const d = wipe.done; wipe.done = null; d(); }
    }
    const g = sp.wipe.clear();
    if (wipe.p <= 0) return;
    g.fillStyle(WIPE.color);
    const view = camView; // 이번 프레임에 정한 카메라 왼쪽 위 (worldView는 그리기 직전에야 바뀐다)
    g.setPosition(view.x, view.y);
    const cx = Math.round(snap(PLAYER.x) + 8 - view.x), cy = Math.round(snap(PLAYER.y) + 8 - view.y);
    const maxR = Math.hypot(Math.max(cx, VW - cx), Math.max(cy, VH - cy)) + 1; // 가장 먼 모서리까지
    const r = maxR * (1 - wipe.p);
    for (let y = 0; y < VH; y++) {
      const dy = y + 0.5 - cy;
      if (Math.abs(dy) >= r) { g.fillRect(0, y, VW, 1); continue; } // 원이 닿지 않는 줄은 통째로
      const half = Math.round(Math.sqrt(r * r - dy * dy));
      g.fillRect(0, y, Math.max(0, cx - half), 1).fillRect(cx + half, y, Math.max(0, VW - cx - half), 1);
    }
  }

  // ---------- 게임 안 웹 창 (Unreal Web Browser 위젯과 같은 역할) ----------
  // 창은 화면 가운데 원으로 열고 닫는다(CSS clip-path). 원을 거는 곳은 창 껍데기(overlay)이고,
  // 안에 들어가는 경매장·가방 화면(iframe, 팀원 화면)은 건드리지 않는다
  // 가방 = 인벤토리 화면. 경매장 화면(/auction)은 경매 담당이 만들면 그대로 열린다
  const TITLES = { '/inventory': '가방', '/auction': '경매장' };
  const IRIS = { shut: 'circle(0 at 50% 50%)', full: 'circle(75% at 50% 50%)', openMs: 450, closeMs: 350 };
  const overlay = $('overlay'), frame = $('ov-frame');
  let openSeq = 0, closing = false;
  function irisOverlay(opening, done) {
    overlay.getAnimations().forEach((a) => a.cancel());
    const a = overlay.animate(
      [{ clipPath: opening ? IRIS.shut : IRIS.full }, { clipPath: opening ? IRIS.full : IRIS.shut }],
      { duration: opening ? IRIS.openMs : IRIS.closeMs, easing: opening ? 'ease-out' : 'ease-in', fill: 'forwards' },
    );
    if (done) a.onfinish = done;
  }
  function openWin(path) {
    if (wipe.target === 1) return; // 이미 여는 중이거나 열려 있다
    keys.clear();
    const show = () => {
      const seq = ++openSeq;
      $('ov-title').textContent = TITLES[path] || '';
      overlay.style.clipPath = IRIS.shut; // 원이 닫힌 채로 띄워 두고
      overlay.classList.remove('hidden');
      // 안의 화면을 다 불러온 뒤에 연다. 빈 화면이 먼저 보이지 않게. 늦어도 1.5초 뒤에는 연다
      let opened = false;
      const reveal = () => {
        if (opened || seq !== openSeq || closing) return;
        opened = true;
        overlay.style.clipPath = '';
        irisOverlay(true);
      };
      on(frame, 'load', reveal, { once: true });
      timers.add(setTimeout(reveal, 1500));
      frame.src = path + '?embed=1'; // embed=1: 창 안에서는 헤더 없이 보여 주자는 표시 (공통 화면이 지원하면 적용된다)
    };
    if (sp.wipe) wipeTo(1, show); // 게임 화면 원이 다 닫히면 창을 연다
    else show(); // 장면을 아직 못 만들었으면 바로 연다
  }
  function closeWin() {
    if (overlay.classList.contains('hidden') || closing) return;
    closing = true;
    irisOverlay(false, () => { // 창 원이 닫힌 뒤 창을 치우고 게임 화면 원을 다시 연다
      overlay.classList.add('hidden');
      overlay.getAnimations().forEach((a) => a.cancel());
      overlay.style.clipPath = '';
      frame.src = 'about:blank';
      closing = false;
      refreshGold(); // 창을 닫으면 골드를 다시 조회한다 (경매장에서 돈이 바뀌었을 수 있다)
      wipeTo(0);
    });
  }
  root.querySelectorAll('[data-open]').forEach((b) => on(b, 'click', (e) => { e.stopPropagation(); openWin(b.dataset.open); }));
  on($('ov-close'), 'click', closeWin);

  // ---------- 페이지 전환: 화면 가운데 픽셀 원 ----------
  // 상단 메뉴로 낚시터를 떠날 때는 창 전체를 가운데로 닫은 뒤 이동하고, 낚시터에 들어오면 가운데에서 연다.
  // 상단 메뉴는 base.html(공통)에 있지만 고치지 않는다. 이 페이지에서만 링크 클릭을 가로챈다.
  // 원의 픽셀 크기를 게임과 맞추려고 창 크기 ÷ SCALE 크기로 그린 뒤 SCALE배로 키운다
  const PAGE_IRIS = { ms: 500, color: '#241a1f' };
  const irisCv = $('iris'), irisG = irisCv.getContext('2d');
  let irisSeq = 0;
  function drawIris(p) { // p: 0 = 다 열림, 1 = 다 닫힘
    irisCv.classList.remove('shut');
    irisCv.style.display = p > 0 ? '' : 'none';
    if (p <= 0) return;
    const w = Math.ceil(innerWidth / SCALE), h = Math.ceil(innerHeight / SCALE);
    if (irisCv.width !== w || irisCv.height !== h) {
      irisCv.width = w; irisCv.height = h;
      irisCv.style.width = w * SCALE + 'px'; irisCv.style.height = h * SCALE + 'px';
    }
    irisG.clearRect(0, 0, w, h);
    irisG.fillStyle = PAGE_IRIS.color;
    const cx = Math.round(w / 2), cy = Math.round(h / 2), r = (Math.hypot(cx, cy) + 1) * (1 - p);
    for (let y = 0; y < h; y++) { // 게임 화면 원(drawWipe)과 같은 방법: 줄마다 원 바깥을 칠한다
      const dy = y + 0.5 - cy;
      if (Math.abs(dy) >= r) { irisG.fillRect(0, y, w, 1); continue; }
      const half = Math.round(Math.sqrt(r * r - dy * dy));
      irisG.fillRect(0, y, Math.max(0, cx - half), 1);
      irisG.fillRect(cx + half, y, Math.max(0, w - cx - half), 1);
    }
  }
  function pageIris(from, to, done) {
    const seq = ++irisSeq, t0 = performance.now();
    const step = (now) => {
      if (seq !== irisSeq || signal.aborted) return; // 그사이 다른 전환이 시작됐거나 화면을 떠났다
      const k = Math.min(1, (now - t0) / PAGE_IRIS.ms);
      drawIris(from + (to - from) * k);
      if (k < 1) requestAnimationFrame(step);
      else if (done) done();
    };
    requestAnimationFrame(step);
  }
  // 원이 다 닫히면 팀 공통 페이지 전환(navigate)으로 이동한다. 이동이 실패해 낚시터에 남으면 원을 다시 연다.
  // 이 핸들러가 preventDefault하므로 공통 링크 처리(page-navigation.js)는 이 클릭에 끼어들지 않는다
  document.querySelectorAll('.topbar a[href^="/"]').forEach((a) => on(a, 'click', (e) => {
    if (e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return; // 새 탭으로 열기는 그대로 둔다
    e.preventDefault();
    keys.clear();
    pageIris(0, 1, () => {
      Promise.resolve(navigate(a.href)).finally(() => { if (!signal.aborted) pageIris(1, 0); });
    });
  }));
  // 뒤로 가기로 돌아오면 브라우저가 닫힌 화면 그대로 되살리므로 다시 연다
  on(window, 'pageshow', (e) => { if (e.persisted) pageIris(1, 0); });

  // ---------- 떠날 때 정리: 다음 화면이 적용되면(signal) 게임·연결·타이머를 모두 멈춘다 ----------
  signal.addEventListener('abort', () => {
    NET.stopped = true;
    const ws = NET.ws;
    NET.ws = null; NET.open = false;
    ws?.close(1000, 'LEAVE');
    clearInterval(pingTimer);
    timers.forEach(clearTimeout);
    keys.clear();
    game?.destroy(true);
    game = null; scene = null;
  }, { once: true });

  // ---------- 시작: 맵 파일과 Phaser를 읽어 크기를 알아낸 뒤 Phaser 게임을 만든다 ----------
  on(window, 'resize', () => (SCALE = fit()));
  Promise.all([loadMap(), loadPhaser()])
    .then(() => {
      if (signal.aborted) return; // 읽는 사이에 다른 화면으로 떠났다
      game = new Phaser.Game({
        type: Phaser.AUTO,
        parent: $('stage'),
        width: VW * SCALE, height: VH * SCALE, // 확대한 화면 크기 그대로. 확대는 카메라 zoom이 한다
        pixelArt: true,
        backgroundColor: '#84c669',
        banner: false,
        audio: { noAudio: true },
        input: { keyboard: false },
        scene: { preload, create, update },
      });
    })
    .catch((e) => {
      if (signal.aborted) return;
      prompt.textContent = '낚시터를 불러오지 못했어요: ' + e.message;
      console.error(e);
      pageIris(1, 0);
    });
}

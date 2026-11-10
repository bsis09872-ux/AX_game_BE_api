import { Fishing } from "./fishing.js";
import { createFishingApi } from "./api.js";
import { createWorldConnection } from "./world-connection.js";

// 낚시터 화면 (templates/game/play.html). Phaser 4로 그린다.
// 장면(Scene) 하나가 preload(그림 읽기) → create(맵·캐릭터 만들기) → update(매 프레임)로 돈다.
// Phaser가 맡는 것: 그림 읽기, 타일맵 그리기, 앞뒤 순서(depth), 카메라 확대, 효과(파티클·흔들기·트윈).
// 직접 하는 것: 픽셀 단위 충돌, HTML로 띄우는 안내문·결과 창·웹 창, 낚시 상태 흐름, WebSocket 멀티플레이, HTTP API.
//
// 팀 공통 화면 규칙(docs/project-structure.md)에 맞춘 점
// - 페이지 HTML의 스크립트는 부분 전환 때 다시 실행되지 않으므로, 동작은 initPlayPage로 pages.js에 "play"로 등록한다
// - 화면을 떠나면(signal) 게임·연결·키 입력·타이머를 모두 정리한다
// - 로그인은 HttpOnly 쿠키다. 토큰을 JavaScript에 저장하지 않고, fetch·WebSocket에 쿠키가 자동으로 붙는다
// - 낚시는 POST /v1/play/fishing-results, 골드는 GET /wallet/balance로 쿠키 인증을 사용한다.

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

export async function createPlayPage({ root, signal, navigate, url = new URL(location.href) }) {
  let active = false;
  let ready, rejectReady;
  const firstFrame = new Promise((resolve, reject) => { ready = resolve; rejectReady = reject; });
  void firstFrame.catch(() => {});
  const readinessTimeout = setTimeout(() => rejectReady(new Error('낚시터 준비 시간이 초과되었습니다.')), 15000);
  signal.addEventListener('abort', () => rejectReady(signal.reason), { once: true });
  const gameEl = root.querySelector('#game');
  if (!gameEl) return;
  // 준비용 host에서 실제 본문으로 이동해도 같은 요소를 참조한다.
  const elements = new Map([...root.querySelectorAll('[id]')].map((element) => [element.id, element]));
  const $ = (id) => elements.get(id);
  const timers = new Set(); // 화면을 떠날 때 지울 setTimeout들
  const on = (target, type, fn, opts = {}) => target.addEventListener(type, fn, { ...opts, signal }); // 떠나면 저절로 풀린다

  // ---------- 화면: 확대 배율(캐릭터 크기)은 고정하고, 창이 커지면 맵을 더 넓게 보여준다 (레벨 맞추기) ----------
  // Phaser 캔버스는 확대한 화면 크기(VW×SCALE)로 만들고, 카메라 zoom으로 SCALE배 키워 그린다. pixelArt: true라 흐려지지 않는다.
  // 원본 크기로 그린 뒤 캔버스를 늘리면 한 번에 SCALE픽셀씩 뚝뚝 움직여서, 화면 1픽셀 단위로 움직이게 이렇게 한다
  const T = 16;
  const ZOOM = 3;         // 정수배 확대. 창이 10칸도 못 보여줄 만큼 좁을 때만 2배로 줄인다
  let W = 320, H = 192;   // 맵 전체 크기(px). 맵 파일을 읽은 뒤 정해진다
  let VW = 320, VH = 192; // 화면에 보이는 크기(px). 창 크기로 정해지고, 맵보다 크지는 않다
  const DEBUG = url.searchParams.has('debug'); // ?debug: 발 상자와 막힌 픽셀을 그린다
  let game = null; // Phaser.Game. 맵 파일을 읽어 크기를 안 뒤에 만든다
  function fit() {
    // 가로: 페이지 폭, 세로: 창 높이에서 상단 메뉴와 아래 안내문 자리를 뺀 만큼
    const top = active ? gameEl.getBoundingClientRect().top + scrollY : 150;
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
  PLAYER.skin = mySkin;
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

  // 서버가 확인한 투척과 결과 상태는 Fishing 한 곳에서 관리한다.
  let clock = 0, state = 'idle', since = 0, bobber = null, caught = null;
  const REEL_MS = 700;
  let reelAt = null;
  const prompt = $('prompt');
  const overlayOpen = () => wipe.target === 1 || !$('overlay').classList.contains('hidden');
  const rodTip = () => ({ x: snap(PLAYER.x) + (PLAYER.face > 0 ? 23 : -8), y: snap(PLAYER.y) + 2 });
  const network = createWorldConnection({
    player: PLAYER, room: MAP_NAME, signal, navigate, status: gameEl,
    onDisconnect: () => { keys.clear(); fishing.disconnect(); },
  });
  const fishing = new Fishing({
    player: PLAYER, signal, network, api: createFishingApi(signal, navigate),
    world: { map, nearLake, nearestWater },
    enabled: gameEl.dataset.fishingEnabled === 'true',
  });
  const flash = (text) => fishing.flash(text);
  const promptText = () => state === 'idle' && atAuction()
    ? '스페이스: 경매장 들어가기' : fishing.prompt();
  function act() {
    if (!active || overlayOpen()) return;
    if (state === 'idle' && atAuction()) return openWin('/auctions');
    fishing.act();
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
    if ((!dx && !dy) || !network.connected || !fishing.canMove || overlayOpen()) return;
    if (state !== 'idle') fishing.cancel();
    if (dx) PLAYER.face = dx > 0 ? 1 : -1;
    PLAYER.dir = dx ? 'side' : dy < 0 ? 'up' : 'down'; // 대각선은 옆모습
    const len = Math.hypot(dx, dy), step = (SPEED * dt) / 1000;
    const ox = PLAYER.x, oy = PLAYER.y;
    const steps = Math.max(1, Math.ceil(step));
    for (let i = 0; i < steps; i++) {
      const nx = PLAYER.x + dx / len * step / steps;
      const ny = PLAYER.y + dy / len * step / steps;
      if (canStand(nx, PLAYER.y)) PLAYER.x = nx;
      if (canStand(PLAYER.x, ny)) PLAYER.y = ny;
    }
    const distance = Math.hypot(PLAYER.x - ox, PLAYER.y - oy);
    walking = distance > 0;
    PLAYER.walked += distance;
  }

  // DB 공유 서버의 전체 상태를 새 화면의 보간 렌더러에 전달한다.
  const INTERP_DELAY = 150;
  const others = new Map();
  const netEl = $('net'), namesEl = $('names');

  function syncOthers() {
    netEl.classList.toggle('on', network.connected);
    netEl.textContent = network.message;
    for (const p of network.others.values()) {
      const view = { ...p, dir: p.direction };
      const existing = others.get(p.id);
      if (!existing) addOther(view);
      else if (existing.receivedAt !== p.receivedAt) pushSample(view);
      others.get(p.id).receivedAt = p.receivedAt;
    }
    for (const id of others.keys()) if (!network.others.has(id)) removeOther(id);
  }

  function addOther(p) {
    removeOther(p.id);
    const label = document.createElement('div');
    label.textContent = p.nickname;
    namesEl.appendChild(label);
    // depth는 그릴 때마다 발밑 y로 맞춘다 (drawOthers)
    const img = (key) => scene.add.image(0, 0, key).setOrigin(0).setVisible(false);
    others.set(p.id, { nickname: p.nickname, buf: [], label, body: img('char_player'), rod: img('ui_rod'), at: null });
    pushSample(p);
  }
  function removeOther(id) {
    const o = others.get(id);
    if (!o) return;
    o.label.remove();
    o.body.destroy(); o.rod.destroy();
    others.delete(id);
  }
  function pushSample(p) {
    const o = others.get(p.id);
    if (!o) return;
    o.buf.push({ t: performance.now(), x: p.x, y: p.y, face: p.face, dir: p.dir, pose: p.pose, skin: p.skin });
    if (o.buf.length > 20) o.buf.shift();
  }
  // 보간: 지금보다 INTERP_DELAY 전 시각이 받은 위치 a와 b 사이 어디쯤인지 계산한다
  function sampleAt(buf, t) {
    while (buf.length > 2 && buf[1].t <= t) buf.shift();
    const a = buf[0], b = buf[1];
    if (!b || t <= a.t) return a;
    const k = Math.min(1, (t - a.t) / (b.t - a.t));
    const d = k < 1 ? a : b; // 방향과 동작은 위치처럼 섞지 않는다.
    return { ...d, x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k };
  }

  function drawOthers(now) {
    const at = performance.now() - INTERP_DELAY;
    others.forEach((o) => {
      if (!o.buf.length) return;
      const p = sampleAt(o.buf, at), px = snap(p.x), py = snap(p.y), depth = feetDepth(py);
      placeAngler(o.body.setDepth(depth), p.dir, p.face, px, py - (p.pose === 'walk' && Math.floor(now / 120) % 2 ? 1 : 0), p.skin);
      o.rod.setVisible(p.pose === 'rod');
      if (p.pose === 'rod') place(o.rod.setDepth(depth + 0.1), px + (p.face > 0 ? 10 : -10), py, p.face < 0);
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
      const response = await fetch('/wallet/balance', { signal, credentials: 'same-origin', cache: 'no-store' });
      if (!response.ok) return;
      const wallet = await response.json();
      if (!signal.aborted) gameEl.querySelectorAll('[data-gold]').forEach((el) => { el.textContent = wallet.available_balance; });
    } catch { /* 공통 세션 관리가 만료와 로그인 이동을 처리한다. */ }
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
    fishing.again(); caught = null; bobber = null;
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
    if (broken) { rejectReady(new Error('게임 리소스를 읽지 못했습니다.')); return; }
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
    if (DEBUG) window.fa = { scene: this, PLAYER, fishing, network }; // ?debug: 콘솔에서 장면·내 위치를 들여다본다

    this.input.on('pointerdown', (pointer) => {
      if (inAuctionArea(pointer.worldX, pointer.worldY, 0)) return openWin('/auctions'); // 경매장 건물·경매사를 클릭
      act();
    });
    this.events.on('render', placeLabels);
    this.events.once('render', ready);
  }

  function update(time, delta) {
    if (!sp.me) return;
    const dt = Math.min(delta, 100);
    if (active) {
      move(dt);
      fishing.update(dt);
    }
    PLAYER.walking = walking;
    PLAYER.pose = fishing.state === 'idle' ? (walking ? 'walk' : 'idle') : 'rod';
    const before = state;
    clock = fishing.clock; state = fishing.state; since = fishing.since; bobber = fishing.bobber;
    if (state !== before && state === 'waiting' && bobber) splash(bobber.x + 8, bobber.y + 6, 12);
    if (state !== before && state === 'bite') scene.cameras.main.shake(160, 0.008);
    if (fishing.caught && caught?.id !== fishing.caught.id) {
      const item = fishing.caught;
      caught = { ...item, key: ITEM_FALLBACK };
      void itemTexture(item.icon).then((key) => { if (!signal.aborted && caught?.id === item.id) caught.key = key; });
    }
    if (state !== before && state === 'caught' && caught) celebrate();
    syncOthers();
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
    } else if ((state === 'waiting' || state === 'bite') && bobber) {
      const dip = state === 'bite' ? 3 : bob;
      line(sp.line, tip, { x: bobber.x + 8, y: bobber.y + 6 + dip });
      place(sp.bobber, bobber.x, bobber.y - 3 + dip);
      if (state === 'bite') {
        const kb = now - since; // 입질이 시작된 뒤 흐른 시간 (이 프레임에서 상태가 바뀌었을 수 있어 다시 잰다)
        const jump = Math.floor(kb / 80) % 2 ? -2 : 0;
        place(sp.exclaim, px, py - 18 + jump);
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
    PLAYER.skin = skin;
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
    if (!active || e.target.closest?.('input, textarea, select, [contenteditable]')) return;
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
  // 가방 = 인벤토리 화면. 경매장 화면(/auctions)은 main에 통합된 경매 담당 화면을 그대로 연다
  const TITLES = { '/inventory': '가방', '/auctions': '경매장' };
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
  on(window, 'message', (event) => {
    if (event.origin === location.origin && event.source === frame.contentWindow
        && event.data?.type === 'auction:close') closeWin();
  });
  // 같은 출처의 가방 화면에서도 포커스가 iframe 안에 있을 때 Esc로 닫는다.
  on(frame, 'load', () => {
    try {
      if (frame.contentWindow.location.origin !== location.origin) return;
      on(frame.contentWindow, 'keydown', (event) => {
        if (event.key === 'Escape') closeWin();
      });
    } catch { /* 외부 출처 화면에는 접근하지 않는다. */ }
  });


  // ---------- 떠날 때 정리: 다음 화면이 적용되면(signal) 게임·연결·타이머를 모두 멈춘다 ----------
  signal.addEventListener('abort', () => {
    timers.forEach(clearTimeout);
    keys.clear();
    game?.destroy(true);
    game?.loop.wake();
    game = null; scene = null;
    if (window.fa?.PLAYER === PLAYER) delete window.fa;
  }, { once: true });

  // ---------- 시작: 맵 파일과 Phaser를 읽어 크기를 알아낸 뒤 Phaser 게임을 만든다 ----------
  on(window, 'resize', () => (SCALE = fit()));
  try {
    await Promise.all([loadMap(), loadPhaser()]);
    signal.throwIfAborted();
    game = new Phaser.Game({
      type: Phaser.AUTO, parent: $('stage'), width: VW * SCALE, height: VH * SCALE,
      pixelArt: true, backgroundColor: '#84c669', banner: false,
      audio: { noAudio: true }, input: { keyboard: false }, scene: { preload, create, update },
    });
    await firstFrame;
    signal.throwIfAborted();
    return {
      activate() {
        active = true;
        SCALE = fit();
        game.scale.updateBounds();
        const { baseSize, canvasBounds, displayScale } = game.scale;
        displayScale.set(baseSize.width / canvasBounds.width, baseSize.height / canvasBounds.height);
        network.connect();
        void refreshGold();
      },
    };
  } finally {
    clearTimeout(readinessTimeout);
  }
}

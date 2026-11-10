# game (낚시터·멀티플레이) 도메인

낚시터 화면(`/play`)과 같은 맵에 있는 사람들의 위치를 주고받는 멀티플레이(WebSocket)를 맡습니다.
돈·아이템이 바뀌는 일은 하지 않습니다. 낚시 결과는 인벤토리, 골드는 지갑의 API를 화면이 그대로 부릅니다.

## 1. 한눈에 보기
| 개념 | 설명 |
|---|---|
| 방(`Room`) | 맵 하나 = 방 하나. 서버 한 대의 메모리에만 있습니다(DB 없음). 최대 인원 `GAME_ROOM_CAPACITY`(기본 20) |
| 플레이어(`Player`) | 방에 들어온 회원 한 명의 위치·보는 방향·동작·캐릭터. 서버가 마지막 위치를 기억합니다 |
| 허브(`WorldHub`) | 방들을 관리하고 1초에 `GAME_TICK_HZ`(기본 10)번, 바뀐 사람의 위치만 모아 나눠 줍니다 |
| 연결(`Connection`) | 한 사람의 WebSocket. 보낼 메시지를 대기열에 넣고 한 곳(writer)에서만 보냅니다 |

## 2. 규칙 (서버가 막는 것)
- **순간이동**: 걷는 속도(초당 60px)의 1.5배 + 16px보다 멀리 한 번에 움직이면 받지 않고 `correct`로 마지막 위치를 돌려줍니다.
- **늦게 온 옛 메시지**: `seq`가 이미 받은 것보다 작거나 같으면 버립니다.
- **모양 검사**: 좌표는 유한한 숫자(±10000 안), `face`는 1/-1, `dir`는 down/up/side, `pose`는 idle/walk/rod, 찌(`bobber`)는 낚싯대를 들었을 때만.
- **한 계정 한 연결**: 같은 계정이 다른 곳에서 들어오면 예전 연결을 `4409`로 끊습니다.
- **메시지 제한**: 위치는 초당 15개, 그 밖은 초당 5개까지. 한 통 `GAME_MAX_MESSAGE_BYTES`(기본 1024)바이트까지.
- **느린 연결**: 보낼 대기열(`GAME_SEND_QUEUE_SIZE`, 기본 64)이 차면 그 사람만 `1013`으로 끊습니다.

## 3. 로그인
- 웹 화면과 같은 HttpOnly 쿠키(`access_token`)를 씁니다. JavaScript는 토큰을 다루지 않습니다.
- WebSocket 연결 요청에 브라우저가 쿠키를 자동으로 붙입니다. 쿠키가 자동으로 붙으므로 **Origin이 `WEB_ORIGIN`과 같을 때만** 받습니다.
- 토큰 확인은 auth의 `authenticate`(서명·만료·로그아웃 여부), 닉네임·활성 여부는 users의 `get_user_summary`로 합니다(`infrastructure/adapters/player_directory.py`). WebSocket은 오래 열려 있으므로 DB 세션은 확인할 때만 잠깐 엽니다.

## 4. API 명세

### 4-1. 화면
| 메서드 | 경로 | 로그인 | 설명 |
|---|---|---|---|
| GET | `/opening` | 없음 | 오프닝 화면. 커튼이 걷히고 로고가 낚여 올라온 뒤 PRESS START. 키·클릭으로 건너뛰고, PRESS START 뒤에는 `/play`로 들어간다 |
| GET | `/play?map=world` | 쿠키 | 낚시터 화면. `map`은 `static/maps/{map}.tmj`(영문·숫자·`_`·`-` 32자, 틀리면 422). 로그인이 안 됐으면 `/login`으로 이동 |

### 4-2. 화면이 부르는 팀 API
| 메서드 | 경로 | 쓰는 곳 |
|---|---|---|
| POST | `/v1/fishing-results` | 낚시 한 번. 201 `{id, definition:{id, code, name, category, rarity, icon, start_price}, status, origin, acquired_at, resale_available_at}` |
| GET | `/v1/wallets/me` | 화면 위 골드 = `available_balance` |
| POST | `/session/refresh` | 401이 오면 한 번 세션을 새로 고친 뒤 다시 시도 |

> 화면 JavaScript는 쿠키만 가지고 있으므로, 위 `/v1` API가 쿠키 로그인을 받아야 동작합니다(공통 수정 PR).
> 낚시 쿨다운은 429 + `Retry-After`(남은 초)로 받으면 화면에 남은 시간을 보여 줍니다.

### 4-3. WebSocket `/v1/ws/world?map=world&skin=angler`
- `map`: 같은 맵끼리만 보입니다(기본 `world`). `skin`: `angler` `girl` `boy` `ghost` `ranger` `knight` (기본 `angler`)
- 메시지는 모두 JSON 글자입니다. ID는 팀 규칙대로 **문자열**입니다.

| 방향 | type | 내용 |
|---|---|---|
| 브라우저 → 서버 | `move` | `{seq, x, y, face, dir, pose, bobber}` 바뀌었을 때만, 최대 0.1초에 한 번. 좌표는 캐릭터 그림의 왼쪽 위 |
| 브라우저 → 서버 | `skin` | `{skin}` 캐릭터 바꾸기 |
| 브라우저 → 서버 | `ping` | `{t}` 10초마다 |
| 서버 → 브라우저 | `welcome` | `{you:{id, nickname}, map, tick_hz, players:[플레이어]}` 들어오자마자 한 번 |
| 서버 → 브라우저 | `join` | `{player:플레이어}` 다른 사람이 첫 위치를 보냄 |
| 서버 → 브라우저 | `state` | `{players:[플레이어(닉네임 없음)]}` 이번 틱에 바뀐 사람만 |
| 서버 → 브라우저 | `leave` | `{id}` |
| 서버 → 브라우저 | `correct` | `{x, y, seq, detail}` 순간이동을 막고 마지막 위치로 되돌림 |
| 서버 → 브라우저 | `pong` | `{t}` |
| 서버 → 브라우저 | `error` | `{detail:{code, message}}` |

플레이어 = `{id, nickname, x, y, face, dir, pose, skin, bobber}`

오류 코드: `UNAUTHORIZED` `FORBIDDEN_ORIGIN` `INVALID_MAP` `INVALID_SKIN` `INVALID_MOVE` `TOO_FAST` `ROOM_FULL` `REPLACED` `TOO_MANY_MESSAGES` `MESSAGE_TOO_BIG` `TEXT_ONLY` `INVALID_MESSAGE` `UNKNOWN_TYPE`

| 종료 코드 | 뜻 | 화면이 하는 일 |
|---|---|---|
| 4401 | 로그인 필요·만료 | 세션을 새로 고친 뒤 다시 연결, 안 되면 로그인 화면 |
| 4403 | 다른 사이트에서 연결 | 다시 연결하지 않음 |
| 4409 | 같은 계정이 다른 곳에서 접속 | 다시 연결하지 않음 |
| 1008 / 1009 | 규칙 위반 / 메시지가 너무 큼 | 다시 연결하지 않음 |
| 1013 | 방이 꽉 참 / 너무 느림 | 1·2·4…최대 30초 뒤 다시 연결 |

## 5. 파일
| 경로 | 역할 |
|---|---|
| `domain/` | `player.py`(위치·순간이동·캐릭터), `room.py`(방), `rate_limit.py`(메시지 제한), `exceptions.py` |
| `application/` | `hub.py`(방 관리·틱), `contracts.py`(PlayerDirectory 계약), `dto.py` |
| `infrastructure/adapters/player_directory.py` | auth·users 서비스로 쿠키 토큰 확인 |
| `presentation/` | `web_router.py`(GET /play), `ws_router.py`(/v1/ws/world), `dependencies.py` |
| `wiring.py` | 허브 하나·접속자 확인기 조립, `GAME_*` 설정 |
| `templates/game/play.html` | 화면 틀(스크립트 없음) |
| `static/game/play.js` | 화면 동작 `initPlayPage`. `pages.js`에 `play`로 등록 |
| `templates/game/opening.html`, `static/game/opening.js`, `static/css/opening.css` | 오프닝 화면. 동작 `initOpeningPage`를 `pages.js`에 `opening`으로 등록. 캔버스 하나에 매 프레임 다시 그린다 |
| `static/css/game.css` | 화면 CSS (`data-page-style`) |
| `static/vendor/phaser/` | Phaser 4.2.1 (MIT, `LICENSE.md`). CDN 대신 파일로 둡니다 |
| `static/sprites/characters/`, `static/sprites/ui/`, `static/sprites/audience/` | 캐릭터 6명×방향 3장과 경매사, 낚시·버튼·단상·망치 UI, 오프닝 관객 14장 (Kenney Tiny 팩 CC0 기반, `static/tiles/LICENSE-kenney.txt`) |
| `static/images/catch-and-bid-logo-opening.png` | 오프닝용 로고 (원본에서 아래 물방울 2개를 지움) |

## 6. 연결에 필요한 공통 수정 (이 폴더만으로는 아직 화면이 뜨지 않습니다)
- `main.py`: `create_game_web_router(get_current_web_user_id)` 등록, `create_world_router(lambda: get_web_settings().origin)`를 `/v1`로 등록
- `static/pages.js`: `play: initPlayPage`, `opening: initOpeningPage` 등록
- `pyproject.toml`·`uv.lock`: `websockets` 추가 (uvicorn이 WebSocket을 열려면 필요)
- `/v1` 로그인 확인이 쿠키도 받기(쓰기 요청은 Origin 확인), 쿨다운 429
- 상단 메뉴에 `/play` 링크

## 7. 테스트
팀 `.gitignore`가 `tests/`를 제외하므로 테스트는 저장소에 올리지 않고 각자 로컬에 둡니다.
낚시터 테스트(`tests/game/test_domain.py` 규칙 5개, `tests/game/test_ws.py` WebSocket 흐름 11개)는 DB 없이 돌고,
WebSocket 테스트는 FastAPI `TestClient`를 쓰므로 테스트용 HTTP 패키지(`httpx2`)가 필요합니다.
```bash
uv run pytest tests/game
```

# 낚시 클라이언트

새 Phaser 화면과 리소스를 기존 백엔드의 인증, DB 공유 월드, 투척 검증에 연결했습니다. 로그인, 가방, 경매, 지갑과 관리자는 이 저장소의 화면과 서비스를 사용합니다. `client`는 화면과 HTTP 진입점을 조립하며 별도의 보상 업무 규칙을 갖지 않습니다.

## 실행과 조작

루트 README에 따라 DB와 환경변수를 준비하고 서버를 실행합니다. 로그인 후 `/v1/play`에 들어갑니다. 낚시 가능한 아이템 카탈로그가 없으면 보상 지급은 실패하므로 개발용 빈 DB에는 시드가 필요합니다. 운영 DB에 시드를 자동 실행하지 않습니다.

- 맵: `/v1/play?map=world`, `lake`, `halloween`. 기본값은 `world`입니다.
- 이동: WASD 또는 방향키. 호숫가에서 클릭/스페이스로 낚싯대를 꺼내고 투척합니다.
- 입질 시간 안에 다시 클릭/스페이스로 당깁니다. 결과는 서버 응답 뒤에 표시합니다.
- 가방과 경매 버튼은 기존 `/inventory`, `/auctions` 화면을 게임 위에 엽니다.
- `/opening`은 로그인 없이 볼 수 있는 오프닝입니다. 게임 진입에는 로그인이 필요합니다.

`DEMO_FISHING_ENABLED` 기본값은 현재 main과 같은 `true`입니다. `false`이면 쿠키 투척/지급 요청은 503이고 Bearer 낚시 라우트는 앱 시작 시 등록되지 않습니다. 월드 접속과 이동은 가능합니다.

## 연결 계약

| 경로 | 인증과 역할 |
| --- | --- |
| `GET /v1/play` | HttpOnly 쿠키로 화면 조회 |
| `WS /v1/ws/world` | HttpOnly 쿠키와 정확한 `WEB_ORIGIN` 검사, DB 기반 접속/위치 공유 |
| `POST /v1/play/casts` | 쿠키와 Origin 검사, `{id, connection_id}`로 투척 시작 |
| `POST /v1/play/casts/cancel` | 쿠키와 Origin 검사, 같은 투척 취소 |
| `POST /v1/play/fishing-results` | 쿠키와 Origin 검사, `{cast_id}`로 검증된 보상 요청 |
| `POST /v1/fishing-results` | Bearer 인증, 같은 `{cast_id}` 검증 사용 |

본문 없는 보상 지급 요청은 더 이상 받지 않습니다. 서버는 투척 소유자, 현재 접속, 호숫가 위치, 입질 시간을 검사합니다. 지급과 투척 결과 기록은 한 트랜잭션으로 저장합니다. 응답을 잃어도 같은 `cast_id`로 재확인하므로 아이템을 중복 지급하지 않습니다. 시작한 투척의 10초 쿨다운은 DB에서 공유합니다.

WebSocket은 `hello`로 방과 캐릭터를 선택하고 `welcome`에서 접속 ID를 받습니다. `move`에는 순번 `seq`를 붙이며 서버가 이동 거리와 벽 충돌을 검사합니다. 이동 확인 응답을 받은 뒤 투척합니다. `state`는 같은 방의 플레이어 목록을 전달합니다. 다른 플레이어의 위치, 방향, 캐릭터와 낚싯대 자세를 표시하며 원격 찌 좌표는 현재 서버 계약에 없습니다.

월드 저장은 PostgreSQL의 `world_presences`, `fishing_attempts`, `fishing_cooldowns`를 사용합니다. 프로세스를 다시 켜거나 두 worker가 같은 DB를 사용해도 접속 목록과 쿨다운을 공유합니다. 한 계정의 새 접속은 이전 접속을 대체합니다. 세션 폐기는 연결 중에도 약 5초 간격으로 재검사합니다.

## 코드 위치

| 파일 | 수정할 내용 |
| --- | --- |
| [web_router.py](web_router.py) | 화면, 쿠키/Bearer HTTP 진입점 |
| [game/main.js](../static/game/main.js) | 첫 프레임 준비와 화면 수명 |
| [game/play.js](../static/game/play.js) | Phaser 장면, 입력, 카메라, 다른 캐릭터 표시 |
| [game/fishing.js](../static/game/fishing.js) | 투척, 입질, 결과 재확인 상태 |
| [game/api.js](../static/game/api.js) | 쿠키 HTTP 호출, 시간 제한 |
| [game/world-connection.js](../static/game/world-connection.js) | WebSocket 연결, 재접속, 이동 확인 |
| [game/play.html](../templates/game/play.html), [game.css](../static/css/game.css) | 화면 요소와 크기 |
| [world](../world/) | 서버 이동/투척 검증과 DB 저장 |
| [auth-session.js](../static/auth-session.js) | 공통 세션 확인과 갱신 |

Inventory가 World를 import하지 않도록 진입점은 `client`에서 조립합니다. World가 Inventory의 기존 지급 규칙을 사용하고 최종 commit을 맡습니다. 새 관리자 도메인이나 별도의 로그인 구현은 추가하지 않습니다.

## page-renderer 규칙

공통 배경과 헤더는 유지하고 `#main-content`의 본문을 교체합니다. `pages.js`의 `play` 초기화와 `preparePage`에 연결되어 있습니다. 낚시터는 화면 밖에서 첫 프레임까지 준비한 뒤 교체하므로 로딩 중 빈 캔버스를 먼저 보이지 않습니다. 준비에 실패하면 이전 화면을 유지합니다. 현재 낚시터 메뉴를 반복 클릭해도 캔버스나 소켓을 다시 만들지 않습니다.

다른 담당자가 페이지를 추가할 때는 [공통 구조 문서](../../docs/project-structure.md)를 따릅니다. HTML의 `data-page`에 대응하는 초기화 함수를 `pages.js`에 등록하고 전달받은 `signal`이 중단되면 이벤트, 타이머와 연결을 해제합니다. 템플릿 안의 script 실행에 의존하지 않습니다. 캔버스처럼 화면 교체 전에 준비가 필요한 경우에만 `preparePage`를 확장합니다.

맵을 바꿀 때는 `static/maps`와 `static/tiles`를 함께 확인합니다. 서버와 브라우저가 같은 Tiled 파일을 읽습니다. 서버 맵 목록과 화면 입력의 허용 목록도 맞춰야 합니다. 맵 변경 후에는 서버의 맵 캐시를 갱신하기 위해 프로세스를 재시작합니다.

## 검증

```bash
node --test scripts/check-fishing-client.mjs
uv run --frozen --with httpx --with playwright python scripts/verify-game-integration.py
uv run --frozen python scripts/verify-domain-boundaries.py
```

브라우저 검증에는 Playwright Chromium 설치가 필요합니다. 통합 스크립트는 설정한 PostgreSQL 서버에 무작위 이름의 **별도 QA DB**를 만들고, 두 ASGI 프로세스와 두 브라우저 세션으로 실행한 뒤 삭제합니다. DB 계정에는 CREATE DATABASE 권한이 필요합니다. 기존 서비스 DB로 앱을 켜지 않습니다.

2026-11-10~11 검증: JS 상태 테스트 6개, 두 계정 이동/캐릭터 공유, 투척 검증, 응답 유실 후 중복 지급 방지, DB 롤백, 동시 지급, 프로세스 재시작, 맵 분리, 반복 메뉴 클릭, 준비 실패 복구, 가방/경매 열기와 로그아웃을 통과했습니다. 공통 세션 갱신을 동시에 세 번 호출해도 한 번만 갱신되는 것을 확인했습니다. 390px 화면의 가로 넘침도 확인했습니다. 모바일 터치 이동 조작은 구현하지 않았습니다.

EC2 준비 조건과 Linux HTTPS/WSS 검증 범위는 [배포 문서](../../docs/ec2-deployment.md)를 확인합니다. 방 정원 30명은 코드의 제한값이며 부하 시험으로 보장한 수용 인원이 아닙니다.

## 리소스 출처

화면과 리소스는 팀의 게임 클라이언트 작업본에서 선별했습니다. 서버의 메모리 방 구현과 본문 없는 보상 지급은 가져오지 않았습니다.

- Phaser 4.2.1: [MIT 라이선스](../static/vendor/phaser/LICENSE.md), 로컬 파일 한 벌 사용
- 캐릭터, UI, 오프닝 관객은 게임 작업본의 Kenney Tiny 팩 기반 리소스입니다. 기존 타일 리소스의 [Kenney 라이선스](../static/tiles/LICENSE-kenney.txt)와 [Land of Pixels 라이선스](../static/tiles/LICENSE-land-of-pixels.txt)를 함께 유지합니다.
- 오프닝용 로고: 팀 게임 작업본의 `catch-and-bid-logo-opening.png`

원본 설명 중 메모리 방, 이전 `/play` 경로, 기존에 없는 테스트 경로와 통신 메시지는 현재 구현에 맞게 수정했습니다.

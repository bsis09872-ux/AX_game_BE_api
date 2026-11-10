# inventory (아이템·인벤토리) 도메인

사용자가 가진 아이템과 서버 카탈로그를 관리합니다. 아이템의 소유와 상태, 변경 이력을 책임지고, 경매장 매물 도메인에는 "예약·해제·소유권 이전" 기능을 제공합니다.

## 1. 한눈에 보기
| 개념 | 설명 |
|---|---|
| 아이템 카탈로그(`ItemDefinition`) | 서버에 등록된 아이템 종류의 공통 정보(이름, 분류, 희귀도, 시작가, 낚시 가중치 등). 누구의 소유도 아닙니다. |
| 인벤토리 아이템(`InventoryItem`) | 특정 사용자가 가진 아이템 한 개. 소유자와 상태를 가집니다. |
| 아이템 이력(`ItemEvent`) | 소유·상태가 바뀔 때마다 쌓이는 기록(수정·삭제 없음). |

- 카탈로그와 인벤토리 아이템은 서로 다른 단위(aggregate)입니다. 인벤토리 아이템은 카탈로그의 번호만 가리킵니다.
- 이력은 인벤토리 아이템과 함께 저장되며, 아이템이 바뀔 때만 생깁니다.

## 2. 상태와 규칙
```
  지급(grant)            판매 예약                 낙찰·소유권 이전
  ───────────▶  OWNED  ───────────▶  LISTED  ───────────▶  OWNED(구매자)
                  ▲                     │
                  └─────────────────────┘
                    예약 해제(유찰·취소)
```
- 상태는 `OWNED`(보관), `LISTED`(경매 판매 예약) 두 가지입니다.
- `OWNED → LISTED`: 소유자 본인만, 재판매 제한 시각(`resale_available_at`) 이후에만 가능합니다.
- `LISTED → OWNED`(판매자): 유찰·취소로 되돌립니다. 획득 시각은 바뀌지 않습니다.
- `LISTED → OWNED`(낙찰자): 소유권이 바뀌고, 획득 시각·출처(`TRADE`)·재판매 제한이 갱신됩니다. 새 소유자는 현재 소유자와 달라야 합니다.
- 소유자가 바뀌는 경로는 `transfer_to` 하나뿐입니다.
- 재판매 제한은 거래로 받은 아이템에 30분입니다.
- 모든 규칙 위반은 도메인이 직접 예외를 던집니다(서비스·라우터의 if-else로 판정하지 않습니다).

획득 출처(`ItemOrigin`): `SEED`, `ADMIN_GRANT`, `REWARD`(낚시), `TRADE`(거래)
이력 종류(`ItemEventType`): `GRANTED`, `LISTED`, `UNLISTED`, `TRANSFERRED`

## 3. 아이템 검증·위조 방지·복제 방지
아이템은 "서버가 정한 값만 갖고", "한 번에 한 곳에만 있고", "바뀐 내역이 남도록" 만들었습니다. 구현한 내용은 아래와 같습니다.

### 3-1. 위조 방지 (클라이언트가 아이템을 만들거나 속성을 정하지 못하게)
| 막으려는 것 | 구현 |
|---|---|
| 아이템을 직접 만들기 | 아이템 생성은 서버 내부 `grant_item` 하나뿐입니다. 클라이언트용 생성·수정·삭제 API가 없습니다. 지급 출처는 `SEED`, `ADMIN_GRANT`, `REWARD`만 허용하고 `TRADE`는 지급할 수 없습니다(거래는 소유권 이전이기 때문입니다). |
| 속성(이름·희귀도·가격) 위조 | 인벤토리 아이템은 카탈로그 번호만 가리키고, 속성은 항상 서버 DB의 카탈로그에서 읽습니다. 요청으로 아이템 속성을 받지 않습니다. 카탈로그의 `name`·`category`는 만든 뒤 바꿀 수 없습니다. |
| 남의 아이템 접근 | 소유자는 요청 값이 아니라 로그인 토큰에서 얻습니다. 남의 아이템 조회는 404(존재 여부를 숨김), 변경 시도는 거절(403)합니다. |
| 낚시 보상 조작 | 결과는 서버가 추첨하고(예측하기 어려운 시스템 난수), 요청 본문이 없으며, 사용자별 쿨다운이 있고, 설정이 켜졌을 때만 라우터를 등록합니다(기본 꺼짐). |
| 내부 값 노출 | 응답 모델이 공개 값만 골라 보여 줍니다(낚시 가중치, `fishable`, 소유자 번호는 비공개). |
| 잘못된 값 | 도메인이 id(`true`/`false` 거부), 시각(시간대 필수), 카탈로그 값(`code`·`name`·분류·희귀도·가격·가중치·`icon` 형식)을 검사하고, 어기면 도메인 예외를 던져 저장하지 않습니다. |

### 3-2. 복제 방지 (같은 아이템이 두 곳에 있거나 두 번 팔리는 것)
| 상황 | 구현 |
|---|---|
| 소유자 | 아이템의 소유자는 한 명(`owner_id` 하나)입니다. 소유자가 바뀌는 경로는 `transfer_to` 하나뿐입니다. |
| 이중 판매 | `OWNED → LISTED`만 예약할 수 있고, 이미 `LISTED`면 다시 예약할 수 없습니다(409). 거래로 받은 아이템은 30분 동안 재판매할 수 없습니다. |
| 동시 요청 | 예약·해제·이전할 때 아이템 행을 `SELECT … FOR UPDATE`로 잠그고, 잠근 뒤의 최신 상태로 판정합니다. 같은 아이템에 동시에 요청이 와도 하나씩 처리됩니다(DB 테스트로 잠금을 확인했습니다). |
| 정산 실패 | 예약·해제·이전은 commit하지 않고 호출한 쪽의 정산 트랜잭션에 묶입니다. 정산이 중간에 실패해 rollback하면 아이템 변경과 이력이 함께 원래대로 돌아갑니다. |
| 잘못된 소유자 | 소유권 이전 때 `from_owner_id`가 현재 소유자와 다르면 거절합니다. |

### 3-3. 변경 추적
- 소유나 상태가 바뀔 때마다 이력(`ItemEvent`)이 한 줄 생깁니다(`GRANTED`, `LISTED`, `UNLISTED`, `TRANSFERRED`). 이력을 수정하거나 삭제하는 코드는 없습니다.
- 아이템 변경과 이력은 같은 트랜잭션으로 저장되어, 이력만 빠지거나 아이템만 바뀌는 일이 없습니다.
- 관리자는 아이템별 이력을 조회할 수 있습니다(`GET /v1/inventory/{item_id}/events`).

### 3-4. 마지막 방어선 (DB 제약)
- 허용값 `CHECK`(분류·희귀도·상태·출처, 가격·가중치 범위), 외래키, `code` 유일 제약, `ON DELETE RESTRICT`(사용 중인 카탈로그와 사용자는 지울 수 없고, 탈퇴는 소프트 삭제)를 둡니다. 애플리케이션을 거치지 않고 잘못된 값을 넣어도 DB가 거절합니다.

### 3-5. 한계
- 낚시 쿨다운과 카탈로그 캐시는 프로세스 메모리에 있어 서버 1개를 전제로 합니다.
- 잠금 대기 시간 제한(`lock_timeout`)과 동시 요청 부하 테스트는 구현하지 않았습니다.
- 같은 `code`로 동시에 생성하면 DB 제약이 막지만 응답이 500일 수 있습니다.

## 4. 폴더 구조
```text
inventory/
├── domain/            순수 파이썬 업무 규칙 (FastAPI·SQLAlchemy·logging을 import하지 않음)
│   ├── enums.py             분류값
│   ├── item_definition.py   아이템 카탈로그 (값 규칙)
│   ├── inventory_item.py    개별 아이템과 상태 전이
│   ├── item_event.py        이력(값 객체)
│   ├── fishing.py           낚시 보상 추첨(가중치)
│   └── exceptions.py        도메인 예외와 코드
├── application/       유스케이스, 트랜잭션 조율
│   ├── service.py           InventoryService (조회, 지급, 관리, 매물 연결용 메서드)
│   ├── fishing_service.py   FishingService (쿨다운 → 추첨 → 지급)
│   ├── contracts.py         필요한 기능의 모양(Protocol)
│   └── dto.py               서비스가 돌려주는 값(DefinitionInfo, ItemInfo, EventInfo)
├── infrastructure/    계약의 구현 (DB, 메모리 등)
│   ├── models.py            SQLAlchemy 모델 3개
│   ├── repositories.py      저장소
│   ├── unit_of_work.py      commit
│   ├── user_lookup.py       회원 조회 어댑터 (users를 wiring으로 연결)
│   ├── current_user.py      현재 사용자 확인 어댑터 (auth를 wiring으로 연결)
│   ├── fishing_cooldown.py  낚시 쿨다운(메모리)
│   ├── cache.py             TTL 캐시(메모리)
│   └── seed.py              시드 데이터
├── presentation/      HTTP 입출력
│   ├── router.py            조회·관리 API
│   ├── fishing_router.py    낚시 API
│   ├── web_router.py        화면 라우터(Jinja2): 내 인벤토리 목록, 아이템 상세, 도감
│   ├── web_filters.py       내 인벤토리 목록의 필터 줄과 주소 만들기
│   ├── schemas.py           요청·응답 모델
│   └── dependencies.py      현재 사용자, 관리자 확인, 서비스 주입
└── wiring.py          부품 조립 (다른 도메인의 wiring을 이용)
```

화면 파일은 `src/` 아래 공통 폴더에 있습니다.
- `src/templates/inventory/`: `index.html`(목록), `detail.html`(상세), `not_found.html`(404), `catalogs.html`(도감), `_macros.html`(금액·시각·필터 줄 조각)
- `src/static/css/inventory.css`: 인벤토리 화면 전용 스타일 (팀 공통 `global.css`는 수정하지 않았습니다)

계층 규칙
- 바깥 계층이 안쪽 계층을 부릅니다: `presentation → application → domain`, `infrastructure`는 계약을 구현합니다.
- `domain`은 다른 계층을 모릅니다.
- 다른 도메인의 `infrastructure`·모델은 import하지 않습니다. 필요한 것은 `contracts.py`에 모양을 정하고, `wiring.py`가 상대 도메인의 wiring으로 연결합니다.
- 라우터는 입력 검증, 서비스 호출, 응답 변환만 합니다. 업무 판정, DB 갱신, commit은 하지 않습니다.
- commit은 서비스가 하고, 오류 시 rollback은 팀 공통 `get_db`가 합니다(저장소는 flush까지만).

## 5. API
모든 경로의 접두어는 `/v1`입니다(화면 제외). 모든 API는 로그인이 필요합니다.

| 메서드 | 경로 | 권한 | 설명 |
|---|---|---|---|
| GET | `/inventory` | 로그인 | 내 아이템 목록 (필터: status, category, rarity / 정렬 / 페이지) |
| GET | `/inventory/{item_id}` | 로그인(본인) | 내 아이템 상세. 남의 아이템은 404 |
| GET | `/item-catalogs` | 로그인 | 아이템 카탈로그 목록 |
| GET | `/item-catalogs/{definition_id}` | 로그인 | 카탈로그 상세 |
| POST | `/item-catalogs` | 관리자 | 카탈로그 생성 (201) |
| PATCH | `/item-catalogs/{definition_id}` | 관리자 | 카탈로그 수정 (name·category는 변경 불가) |
| DELETE | `/item-catalogs/{definition_id}` | 관리자 | 카탈로그 삭제 (204, 사용 중이면 거절) |
| GET | `/inventory/{item_id}/events` | 관리자 | 아이템 이력 (오래된 순, 페이지) |
| POST | `/fishing-results` | 로그인 | 낚시 (201, 설정이 켜진 경우만 등록) |

- 응답의 ID는 문자열이고, 일반 사용자 응답에는 낚시 가중치(`weight`, `fishable`)와 소유자 번호가 없습니다.
- 소유자는 요청 값이 아니라 인증 정보에서 얻습니다.

### 화면 (Jinja2)
화면 경로는 `/v1` 접두어 없이 등록하고, 쿠키 로그인을 씁니다. 로그인 확인은 `main`이 함수를 넘겨주는 방식입니다(`create_inventory_web_router(current_user_id, wallet_reader)`: 뒤의 것은 선택이며 가방의 지갑 박스용 읽기 함수. 헤더의 사용 가능 금액은 공통 헤더가 채운다).

| 경로 | 권한 | 설명 |
|---|---|---|
| `/inventory` | 로그인 | 내 가방(20칸 격자, 20개씩). 칸을 누르면 `?item={번호}`로 선택되어 오른쪽 패널에 시작가·'경매 시작'(경매 등록 화면 `/auctions/new`로 전송)·'상세 보기'·'도감 보기'가 나온다. 경매 중(LISTED) 칸은 회색. 격자 아래에 상태·분류·희귀도 필터와 정렬 버튼. `main`이 읽기 함수 둘을 넘기면 헤더 골드와 지갑 박스(사용 가능·묶인 골드)도 보인다 |
| `/inventory/{item_id}` | 로그인(본인) | 내 아이템 상세. 없는 아이템이나 남의 아이템은 JSON이 아니라 '찾을 수 없습니다' 화면(404)으로 응답(존재 여부를 알려 주지 않음). '아이템 도감 보기'는 도감의 해당 아이템 줄(`#item-번호`)로 이동 |
| `/item-catalogs` | 로그인 | 도감(카탈로그 목록). 분류·희귀도 필터, 한 페이지에 모두 표시(최대 100개), 줄마다 `id="item-번호"` |

- 시작가는 천 단위 콤마와 `GOLD` 단위로, 시각은 초 단위까지 `UTC`로 표시합니다.
- 필터 링크는 나머지 필터를 유지하고 1쪽으로 돌아가며, 기본 정렬은 주소에 넣지 않습니다. 값이 틀리면 서비스를 부르지 않고 422입니다.
- 개인 화면이라 `Cache-Control: no-store`를 보냅니다.
- 도감은 필터가 두 개라 템플릿이 주소를 만들고, 인벤토리 목록은 값이 네 개이고 쪽이 있어 `web_filters.py`가 만듭니다.

## 6. 다른 도메인에 공개하는 기능
`InventoryService` (경매 매물·정산 쪽에서 사용합니다)

| 메서드 | commit | 설명 |
|---|---|---|
| `get_item(item_id)` | 안 함 | 소유자 확인 없이 읽기(거래 기록 스냅샷용) |
| `reserve_for_listing(item_id, by_owner_id, now, listing_id)` | **안 함** | `OWNED → LISTED`. 행을 잠그고 판정 |
| `release_from_listing(item_id, by_owner_id, now, listing_id)` | **안 함** | `LISTED → OWNED`(판매자 그대로) |
| `transfer_to(item_id, new_owner_id, now, listing_id, trade_id, from_owner_id)` | **안 함** | `LISTED → OWNED`(낙찰자). `from_owner_id`가 현재 소유자와 다르면 거절 |
| `grant_item(definition_id, owner_id, origin, now, actor_id)` | 함 | 아이템 새로 지급 |

- 위 `commit 안 함` 메서드는 **호출한 쪽의 정산 트랜잭션**이 commit·rollback합니다. 정산이 실패해 rollback하면 아이템 변경과 이력이 함께 되돌아갑니다.
- 아이템을 먼저 잠그고(`FOR UPDATE`) 잠근 뒤의 최신 상태로 판정합니다.

인벤토리가 다른 도메인에 요청하는 것(`contracts.py`)
- `UserLookup`: 활성 사용자 번호만 돌려주는 기능 (users)
- `CurrentUserProvider`: 액세스 토큰으로 요청한 사람(번호, 역할) 확인 (auth)

## 7. 오류 코드
| 코드 | 상태 | 의미 |
|---|---|---|
| `ITEM_RULE_VIOLATION` | 400 | 값 규칙 위반 |
| `DEFINITION_IMMUTABLE` | 400 | name·category 변경 시도 |
| `RESALE_NOT_AVAILABLE` | 400 | 재판매 제한 시간 전 |
| `DEFINITION_CODE_DUPLICATE` | 400 | 이미 있는 code로 생성 |
| `DEFINITION_IN_USE` | 400 | 사용 중인 카탈로그 삭제 |
| `NOT_OWNER` | 403 | 소유자가 아님 |
| `ITEM_NOT_FOUND`, `DEFINITION_NOT_FOUND`, `OWNER_NOT_FOUND` | 404 | 대상 없음 |
| `ITEM_STATE_CONFLICT` | 409 | 상태가 맞지 않음 |
| `FISHING_COOLDOWN` | 500 | 낚시 간격 안 지남 |
| `FISHING_NO_REWARD` | 500 | 낚시 후보 카탈로그 없음 |

- 오류 응답은 팀 공통 핸들러가 `{"detail": {"code", "message"}}` 모양으로 만듭니다.
- 낚시 두 오류는 별도 분류 없이 분류되지 않은 오류(500)로 응답됩니다. 현재 범위에서는 이 상태를 유지합니다.

## 8. 설정
| 환경 변수 | 기본값 | 설명 |
|---|---|---|
| `DEMO_FISHING_ENABLED` | 켜짐 | 켜져 있어야 낚시 라우터를 앱에 등록합니다. `false`·`0`·`no`·`off`로 두면 끕니다 |
| `CACHE_TTL_SECONDS` | 15 | 카탈로그 캐시 만료 시간(초). 0 이하나 숫자가 아니면 시작할 때 오류 |

## 9. 구현 현황과 아직 연결되지 않은 것
구현 완료: 조회 API, 관리자 카탈로그 API, 이력 API, 낚시, 화면(내 인벤토리 목록·필터·정렬, 아이템 상세, 도감), 캐시, 접근 로그

아직 연결되지 않은 것 (협의·확인 후 진행)
- 회원 탈퇴 시 아이템 처리: 보류
- 인벤토리 화면의 메뉴·로그인 이동, 화면 소유: 화면 담당과 협의
- 아이템 아이콘: 그림 파일은 `src/static/sprites/item_<icon>.png`(16×16)에 있고(`icon` 값 앞에 `item_`을 붙인 이름, 예: `fish_carp` → `item_fish_carp.png`), `icon` 값은 영문 소문자로 시작하는 영문 소문자·숫자·밑줄 1~50자만 허용합니다. 화면 적용은 진행 중입니다. 파일이 없는 `icon`(예: `default`)은 `item_gift_box.png`로 대체합니다
- 도감은 항목이 100개를 넘으면 한 페이지 방식과 줄 이동 링크가 맞지 않을 수 있습니다

## 10. 캐시와 백그라운드
캐시(`infrastructure/cache.py`)
- 카탈로그 **목록·상세 조회**에만 메모리 TTL 캐시를 씁니다. 생성·수정·삭제 commit 뒤에 캐시 전체를 지웁니다.
- 예약·이전·지급 판정, 내 인벤토리, 낚시에는 쓰지 않습니다(판정은 항상 DB 최신값).
- 한계: 프로세스 메모리라 서버를 여러 개 띄우면 TTL 동안 값이 어긋날 수 있습니다.

백그라운드
- `GET /v1/inventory` 응답을 보낸 뒤 접근 로그 한 줄(사용자 번호, 건수)을 남깁니다.
- 상태를 바꾸는 일은 백그라운드로 넘기지 않습니다. 토큰·필터 값·이름은 로그에 넣지 않습니다.

## 11. 낚시
- `POST /fishing-results`: 쿨다운(사용자별 10초, 메모리) → 후보 카탈로그(`fishable`이고 `weight > 0`) 조회 → 가중치 추첨 → `REWARD` 출처로 지급.
- 낚시 결과는 서버가 정합니다(예측하기 어려운 시스템 난수 사용).
- 쿨다운 기록은 프로세스 메모리라 서버를 다시 켜면 사라집니다.

## 12. 구현 규칙
- 시각은 `now`를 인자로 받습니다(도메인이 시계를 직접 읽지 않습니다. UTC 시간대 포함).
- 이력 누락 방지를 위해 요청마다 DB에서 새로 읽고, 도메인 객체를 요청 사이에 보관하지 않습니다.
- 로그는 `logging.getLogger(__name__)`, 저장 성공 로그는 commit 뒤에 남기고 번호만 담습니다.
- 규칙 판정은 도메인 안에 둡니다. 서비스는 존재·중복·사용 중 여부만 판정합니다.
- 서비스가 돌려주는 값은 DTO입니다(도메인 객체를 밖으로 내보내지 않습니다).

## 13. 시드 데이터
- `python -m inventory.infrastructure.seed` (저장소 루트에서 `PYTHONPATH=src`, 앱을 한 번 켜서 테이블이 만들어진 뒤)
- 카탈로그 13개(각각 설명 포함), 시연용 아이템 24개(이력 24건), 시연 소유자는 사용자 1·2·3입니다.
- 여러 번 실행해도 안전합니다(카탈로그는 code로 중복을 건너뜀).
- 이미 있는 카탈로그는 덮어쓰지 않으므로, 설명이 없던 기존 데이터에는 시드를 다시 돌려도 설명이 채워지지 않습니다.

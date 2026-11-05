# auction / domain

엔티티, 도메인 규칙, Repository 인터페이스를 둔다. **DB와 FastAPI를 모른다.** (순수 Python + `shared` 예외만 import)

- Entity: 재료 (데이터 + 스스로 지키는 규칙)
- Repository: 레시피/지시사항 (무엇을 저장하고 찾을지만 정의, 구현은 infrastructure)

## 폴더 구조

```
src/auction/domain/
├─ listings/
│   ├─ __init__.py
│   ├─ entities.py       # ListingStatus, AUCTION_DURATION, Listing
│   └─ repositories.py   # ListingRepository (ABC)
├─ trades/
│   ├─ __init__.py
│   ├─ entities.py       # Trade
│   ├─ repositories.py   # TradeRepository (ABC)
│   └─ policies.py       # 연속 낙찰 제한 상수 + is_bid_banned  ← 신규
├─ __init__.py
└─ README.md
```

| 파일                       | 내용                                                                          |
| -------------------------- | ----------------------------------------------------------------------------- |
| `listings/entities.py`     | `ListingStatus` enum, `AUCTION_DURATION` 상수, `Listing` 엔티티 + 규칙 메서드 |
| `listings/repositories.py` | `ListingRepository` 인터페이스                                                |
| `trades/entities.py`       | `Trade` 엔티티 (불변) + 팩토리 메서드                                         |
| `trades/repositories.py`   | `TradeRepository` 인터페이스                                                  |
| `trades/policies.py`       | 낙찰 기록으로 판단하는 규칙 (AUC-08 연속 낙찰 제한)                           |

### 의존 방향

- `trades` → `listings` import 허용 (같은 BC, `Trade.from_sold_listing`이 `Listing`을 받음)
- `listings` → `trades` import 금지
- domain → application / infrastructure / presentation import 금지

### 다른 계층과의 관계 (참고)

| 위치                                | 내용                                                                                    |
| ----------------------------------- | --------------------------------------------------------------------------------------- |
| `application/listings/service.py`   | 등록, 조회, 입찰, `promote_next`                                                        |
| `application/trades/service.py`     | 내 낙찰 내역, 내 판매 내역                                                              |
| `application/auction_service.py`    | 마감 → 정산 → 다음 매물 공개 (listings + trades 조율)                                   |
| `application/constructs.py`         | 다른 도메인 인터페이스 (`WalletPort`, `InventoryPort`) — 팀 통일, `ports.py` 사용 안 함 |
| `infrastructure/{listings,trades}/` | ORM `models.py`, Repository 구현 `repositories.py`                                      |
| `infrastructure/scheduler.py`       | 마감 실행 주기만 담당 (`auction_service.close_expired(now)` 호출)                       |

> CANCELLED는 MVP에서 제외. 매물 취소 기능이 확정되면 `QUEUED → CANCELLED`만 추가한다.

## 기능 목록 (MVP)

| ID     | 기능             | 한 줄 설명                                                                          | domain 관련 위치                         |
| ------ | ---------------- | ----------------------------------------------------------------------------------- | ---------------------------------------- |
| AUC-01 | 매물 등록        | 내 아이템을 시작가와 함께 등록. 같은 종류가 공개 중이면 QUEUED, 아니면 바로 BIDDING | `Listing.create`, `start`                |
| AUC-02 | 매물 목록 조회   | BIDDING 매물만 조회 (종류별 1개)                                                    | `ListingRepository.list_bidding`         |
| AUC-03 | 매물 상세 조회   | 현재 최고가, 남은 시간                                                              | `Listing.remaining`                      |
| AUC-04 | 입찰             | 현재가보다 높은 금액으로 입찰                                                       | `Listing.place_bid`                      |
| AUC-05 | 자동 마감 + 정산 | 경매 시간이 지나면 낙찰(SOLD) 또는 유찰(FAILED)                                     | `is_expired`, `mark_sold`, `mark_failed` |
| AUC-06 | 다음 매물 공개   | 같은 종류의 다음 QUEUED 매물을 BIDDING으로                                          | `ListingRepository.next_queued`, `start` |
| AUC-07 | 내 낙찰 내역     | 내가 낙찰받은 거래 목록                                                             | `TradeRepository.list_by_buyer`          |
| AUC-08 | 연속 낙찰 제한   | 30분 내 3건 이상 낙찰 시 마지막 낙찰 시각부터 10분간 새 입찰 금지                   | `trades/policies.is_bid_banned`          |
| AUC-09 | 재판매 제한      | 낙찰받은 아이템은 30분간 등록 금지 (**inventory 담당**)                             | 없음 (에러 전달만)                       |
| AUC-10 | 내 판매 내역     | 내가 판매한 거래 목록                                                               | `TradeRepository.list_by_seller`         |

## 공통 규칙

- 모든 `now`는 **인자로 받는다.** 엔티티 안에서 `datetime.now()`를 호출하지 않는다 (테스트에서 시간을 제어하기 위해).
- 모든 `now`는 **timezone 포함 UTC 값**이어야 한다. naive datetime은 `ValueError` (inventory와 같은 규칙).
- 검사 순서는 **상태 → 시간 → 사람 → 금액**으로 고정한다. 같은 상황에서 항상 같은 에러가 나도록.

## 예외

`shared/core` 공통 예외를 사용한다. HTTP 변환은 핸들러가 하며, 도메인을 직접 호출하면 Python 예외로 발생한다 (`pytest.raises`로 검증).

| 예외                      | HTTP | 언제 쓰나                                                              |
| ------------------------- | ---- | ---------------------------------------------------------------------- |
| `BusinessRuleError`       | 400  | 언제 요청해도 안 되는 것 (규칙 위반)                                   |
| `ConflictError`           | 409  | 요청은 맞지만 **매물의 현재 상태** 때문에 안 되는 것                   |
| `NotFoundError`           | 404  | 대상 없음 → 엔티티가 아니라 **서비스에서** 발생                        |
| `ValueError` 등 일반 예외 | 500  | 개발자 실수 (naive datetime, id 없는 listing 등). 내부 원인 노출 안 됨 |

---

## Listing (`listings/entities.py`)

### 파일 구성

| 순서 | 블록                                      | 목적                                                 |
| ---- | ----------------------------------------- | ---------------------------------------------------- |
| ①    | import                                    | 표준 라이브러리 + `shared` 예외만                    |
| ②    | `ListingStatus(str, Enum)`                | QUEUED / BIDDING / SOLD / FAILED                     |
| ③    | `AUCTION_DURATION = timedelta(minutes=6)` | 경매 진행 시간                                       |
| ④    | `_ALLOWED_TRANSITIONS`                    | 허용된 상태 전이 표. 상태 규칙의 단일 기준           |
| ⑤    | `@dataclass Listing` 필드                 | ERD 컬럼과 1:1. 필수 값 앞, 기본값 있는 값 뒤        |
| ⑥    | `create()`                                | 생성 규칙을 강제하는 유일한 입구                     |
| ⑦    | 행위 메서드                               | `start`, `place_bid`, `mark_sold`, `mark_failed`     |
| ⑧    | 조회 메서드                               | `is_expired`, `has_bidder`, `remaining`              |
| ⑨    | 내부 헬퍼                                 | `_transition_to`, `_require_status`, `_ensure_aware` |

### 필드

| 필드               | 타입             | 비고                                       |
| ------------------ | ---------------- | ------------------------------------------ |
| seller_id          | int              | auction 역할 이름 (값은 users id, FK 없음) |
| inventory_item_id  | int              | inventory id 값 (FK 없음)                  |
| item_definition_id | int              | 대기열 묶음 기준 (FK 없음)                 |
| start_price        | int              | 0보다 큼                                   |
| created_at         | datetime         | 대기열 등록 시각                           |
| status             | ListingStatus    | 기본값 QUEUED                              |
| current_bidder_id  | int \| None      | auction 역할 이름, 현재 최고 입찰자        |
| current_bid_amount | int \| None      | 현재 최고 입찰액                           |
| started_at         | datetime \| None | 실제 공개 시각                             |
| ends_at            | datetime \| None | 입찰 마감 시각                             |
| closed_at          | datetime \| None | 종료 처리 완료 시각                        |
| updated_at         | datetime \| None | 마지막 변경 시각                           |
| id                 | int \| None      | 저장 전 None                               |

### 상태 전이

허용된 방향만 가능하고, 그 외는 `ConflictError`.

```
QUEUED  → BIDDING   공개 시작
BIDDING → SOLD      입찰자 있음 + 정산 성공
BIDDING → FAILED    입찰자 없음 또는 정산 실패
SOLD / FAILED       종료 상태, 더 이상 변경 불가
```

- 상태는 반드시 `_transition_to()`로만 바꾼다. `self.status = ...` 직접 대입 금지.
- `Listing(...)` 직접 호출은 Repository가 DB 값을 복원할 때만 쓴다. 새 매물은 항상 `create()`.

### updated_at 갱신

- 성공한 `create`, `start`, `place_bid`, `mark_sold`, `mark_failed`에서 `updated_at = now`로 설정한다.
- `create`는 생성 시 초기화하고, 상태 전이에 따른 갱신은 `_transition_to()`에서 처리한다.
- `place_bid`는 모든 검사를 통과한 뒤 메서드 안에서 직접 갱신한다.
- 조회 메서드(`is_expired`, `has_bidder`, `remaining`)와 실패한 행위는 갱신하지 않는다.
- DB `onupdate`에 맡기지 않고 도메인에서 전달받은 `now`로 설정한다.

### `create(seller_id, inventory_item_id, item_definition_id, start_price, now)` — AUC-01

- `start_price <= 0` → `BusinessRuleError` (`INVALID_START_PRICE`)
- `status = QUEUED`, `created_at = now`, `updated_at = now`
- 본인 소유 확인은 **Service**가 한다 (inventory 정보 필요).
- 재판매 제한(AUC-09)은 Service가 `reserve_for_listing`을 호출할 때 **inventory가 판단**한다. `ResaleNotAvailableError`(BusinessRuleError, 400)가 나면 auction은 잡지 않고 그대로 전달하고, 트랜잭션이 롤백되어 listing도 저장되지 않는다.

### `start(now)` — AUC-01, AUC-06

- QUEUED가 아니면 `ConflictError` (`INVALID_LISTING_STATE`)
- `started_at = now`, `ends_at = now + AUCTION_DURATION`, `status = BIDDING`

### `place_bid(bidder_id, amount, now)` — AUC-04

| 순서 | 조건                                         | 예외              | code                     |
| ---- | -------------------------------------------- | ----------------- | ------------------------ |
| 1    | BIDDING 아님                                 | ConflictError     | `LISTING_NOT_BIDDING`    |
| 2    | `now >= ends_at`                             | ConflictError     | `LISTING_CLOSED`         |
| 3    | 입찰자 == 판매자                             | BusinessRuleError | `SELF_BID_NOT_ALLOWED`   |
| 4    | 입찰자 == 현재 최고 입찰자                   | ConflictError     | `ALREADY_HIGHEST_BIDDER` |
| 5    | 첫 입찰인데 `amount <= start_price`          | BusinessRuleError | `BID_TOO_LOW`            |
| 6    | 이후 입찰인데 `amount <= current_bid_amount` | ConflictError     | `BID_OUTBID`             |

- 통과 시 `current_bidder_id`, `current_bid_amount` 갱신
- 최소 증가 단위 없음 (1이라도 크면 됨)
- 6번이 409인 이유: 대부분 화면을 본 사이 다른 사람이 먼저 올린 경우라서, 클라이언트가 새로고침하도록 유도한다.

입찰 가능 금액과 연속 낙찰 제한(AUC-08)은 **Service**가 확인한다.

```
쓸 수 있는 돈 = wallet 잔액 - ListingRepository.sum_leading_bids(user_id)
쓸 수 있는 돈 >= amount 여야 입찰 가능
```

다른 사람이 더 높게 입찰하면 `current_bidder_id`가 바뀌므로 묶여 있던 금액은 계산에서 자동으로 빠진다. 별도 예약금 해제 처리는 없다.

### 조회 메서드 — AUC-03, AUC-05

- `is_expired(now)`: `return self.ends_at is not None and now >= self.ends_at`. `ends_at=None`인 QUEUED 매물은 예외 없이 False를 반환한다.
- `has_bidder()`: `current_bidder_id is not None`
- `remaining(now)`: BIDDING이면 `max(ends_at - now, 0)`, 아니면 `None`

### `mark_sold(now)` / `mark_failed(now)` — AUC-05

- 마감 전이거나 BIDDING이 아니면 `ConflictError` (`LISTING_NOT_CLOSABLE`)
- `mark_sold`는 입찰자가 없어도 `ConflictError`
- `closed_at = now`

마감 순서 (`application/auction_service.py`, 매물별 하나의 트랜잭션):

1. 이미 종료된 매물이면 건너뜀 (멱등)
2. 입찰자 없음 → `mark_failed` → 아이템 예약 해제
3. 입찰자 있음 → 구매자 출금 시도
   - 잔액 부족 → `mark_failed` → 아이템 예약 해제
   - 성공 → 판매자 입금 → 아이템 소유권 이전 → `mark_sold` → `Trade.from_sold_listing` 저장
4. 같은 item_definition의 다음 QUEUED 매물 `start(now)` (AUC-06, `listings/service.promote_next`)

---

## Trade (`trades/entities.py`)

### 필드 — `@dataclass(frozen=True)`

| 필드                 | 타입        | 비고                        |
| -------------------- | ----------- | --------------------------- |
| listing_id           | int         | 같은 BC라 FK 유지, UNIQUE   |
| seller_id            | int         | auction 역할 이름 (FK 없음) |
| buyer_id             | int         | auction 역할 이름 (FK 없음) |
| item_name_snapshot   | str         | 체결 시점 아이템 이름       |
| seller_name_snapshot | str         | 체결 시점 판매자 이름       |
| buyer_name_snapshot  | str         | 체결 시점 구매자 이름       |
| price_snapshot       | int         | 낙찰가, 0보다 큼            |
| completed_at         | datetime    | 체결 시각                   |
| id                   | int \| None | 저장 전 None                |

- `seller_id`, `buyer_id`, `bidder_id`는 auction 컨텍스트의 **역할 이름**이다. 값은 users의 id와 같지만 FK 없이 값만 저장한다.
- `frozen=True`: 생성 후 변경 불가를 언어 차원에서 보장. Repository는 저장 후 `dataclasses.replace(trade, id=new_id)`로 반환한다.

### `from_sold_listing(listing, item_name, seller_name, buyer_name, now)`

- 거래를 만드는 유일한 입구
- `listing.status != SOLD` → `ConflictError` (`LISTING_NOT_SOLD`)
- `listing.id`, `current_bidder_id`, `current_bid_amount`가 없으면 `ValueError` (버그)
- `seller_id = listing.seller_id`, `buyer_id = listing.current_bidder_id`, `price_snapshot = listing.current_bid_amount`
- 매물당 1건 (`listing_id` UNIQUE, DB에서 한 번 더 보장)

---

## 정책 (`trades/policies.py`)

낙찰 기록 여러 건을 봐야 판단할 수 있는 규칙. 엔티티 하나로는 판단할 수 없어서 순수 함수로 둔다. 입력은 시각 값만 받는다.

### 상수

```python
WIN_LIMIT_COUNT = 3                        # 이 횟수 이상 낙찰하면
WIN_LIMIT_WINDOW = timedelta(minutes=30)   # 이 시간 안에
BID_BAN_DURATION = timedelta(minutes=10)   # 이 시간 동안 새 입찰 금지
```

### `is_bid_banned(recent_win_times, now) -> bool` — AUC-08

- `recent_win_times`: 최근 낙찰 시각 최신순, 최대 `WIN_LIMIT_COUNT`개 (`TradeRepository.recent_win_times`)
- 개수 < `WIN_LIMIT_COUNT` → False
- (가장 최근 − `WIN_LIMIT_COUNT`번째) <= `WIN_LIMIT_WINDOW` 이고 `now < 가장 최근 + BID_BAN_DURATION` → True
- 조회는 가능하고 새 입찰만 막는다. 제한 전에 해 둔 입찰의 낙찰은 막지 않는다.
- 호출 위치: `application/listings/service.py` 입찰 흐름 → True면 `BusinessRuleError` (`BID_BANNED`)
- 별도 테이블 없이 `trades.buyer_id`, `trades.completed_at`만으로 계산한다.

### AUC-09 재판매 제한 → inventory 담당 (auction에 로직 없음)

- inventory `transfer_to`가 낙찰 시 `origin = TRADE`, `resale_available_at = now + 30분`(`DEFAULT_RESALE_DELAY`)을 설정한다.
- inventory `reserve_for_listing`이 `now < resale_available_at`이면 `ResaleNotAvailableError`를 던진다.
- 낚시 보상(`grant`)으로 얻은 아이템은 제한되지 않는다.
- auction은 `transfer_to`에 추가로 넘길 값이 없다.

---

## Repository 인터페이스

구현은 `infrastructure/{listings,trades}/repositories.py`.

### `listings/repositories.py` — ListingRepository

| 메서드                                               | 용도                                             |
| ---------------------------------------------------- | ------------------------------------------------ |
| `get(listing_id) -> Listing \| None`                 | 단건 조회                                        |
| `get_for_update(listing_id) -> Listing \| None`      | 행 잠금(`FOR UPDATE`). 입찰·마감용               |
| `list_bidding(page) -> list[Listing]`                | AUC-02. BIDDING만 반환 (대기 매물은 서버가 숨김) |
| `exists_bidding(item_definition_id) -> bool`         | 같은 종류 공개 매물 존재 여부                    |
| `next_queued(item_definition_id) -> Listing \| None` | 같은 종류 QUEUED 중 `created_at` 가장 오래된 1건 |
| `list_expired_bidding(now) -> list[Listing]`         | BIDDING이고 `ends_at <= now`                     |
| `sum_leading_bids(user_id) -> int`                   | user가 최고 입찰자인 BIDDING 입찰액 합           |
| `save(listing) -> Listing`                           | 저장                                             |

DB 제약: `UNIQUE (item_definition_id) WHERE status = 'BIDDING'`, `INDEX (item_definition_id, status, created_at)`, `INDEX (status, ends_at)`, `INDEX (current_bidder_id, status)`

### `trades/repositories.py` — TradeRepository

| 메서드                                                | 용도                        |
| ----------------------------------------------------- | --------------------------- |
| `save(trade) -> Trade`                                | 저장 (id 채워서 반환)       |
| `get_by_listing(listing_id) -> Trade \| None`         | 단건 조회                   |
| `list_by_buyer(buyer_id, page) -> list[Trade]`        | AUC-07 내 낙찰 내역, 최신순 |
| `list_by_seller(seller_id, page) -> list[Trade]`      | AUC-10 내 판매 내역, 최신순 |
| `recent_win_times(buyer_id, limit) -> list[datetime]` | AUC-08 판단 재료            |

DB 제약: `UNIQUE (listing_id)`, `INDEX (buyer_id, completed_at)`, `INDEX (seller_id, completed_at)`

---

## 작성 순서

1. `listings/entities.py`: enum, 상수, 전이 표, 필드 → 헬퍼 3개 → `create`, `start`, `place_bid` → 조회 메서드 → `mark_sold`, `mark_failed`
2. `trades/entities.py`: `Trade.from_sold_listing`
3. `trades/policies.py`: `is_bid_banned`
4. `listings/repositories.py`, `trades/repositories.py` (ABC)

메서드 하나를 만들 때마다 도메인 단위 테스트를 붙인다 (DB 없이 바로 검증 가능).

---

## 기존 README 대비 변경 사항

1. `CANCELLED`를 MVP 상태에서 제외
2. 첫 입찰 조건 `>= start_price` → `> start_price` (시작가 "초과"만 허용)
3. 같은 사람 연속 최고 입찰 → 금지로 확정
4. 입찰 반환값 "직전 최고 입찰자와 금액" 삭제 (예약금 해제 대신 쓸 수 있는 돈 계산 방식)
5. 마감 메서드를 `mark_sold` / `mark_failed`로 분리 (입찰자가 있어도 정산 실패 시 FAILED)
6. 경매 시간 6분 확정, `listings/entities.py`의 `AUCTION_DURATION` 상수
7. AUC-08 연속 낙찰 제한 추가 (`trades/policies.py`, `recent_win_times`)
8. AUC-09 재판매 제한은 inventory 담당으로 확정. auction은 에러를 그대로 전달
9. 다른 도메인 인터페이스 파일은 `ports.py` 대신 `application/constructs.py`로 팀 통일
10. trades에 `seller_id` 추가 (auction 역할 이름, FK 없음), AUC-10 내 판매 내역 추가
11. 폴더 구조를 `listings/`, `trades/` 하위 폴더 + `repositories.py`로 정정 (`enums.py`, `constants.py`, `repository.py` 없음)
12. 예외를 실제 공통 예외(BusinessRuleError 400 / NotFoundError 404 / ConflictError 409)로 정정, 메서드별 예외·code 매칭 추가

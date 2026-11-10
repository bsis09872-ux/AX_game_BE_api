# auction / infrastructure

auction 바운디드 컨텍스트(BC)의 infrastructure 계층이다.
SQLAlchemy로 도메인의 저장·조회 계약을 구현하고, Adapter로 다른 도메인 서비스를 연결한다.

## 폴더 구조

```text
infrastructure/
├─ listings/
│  ├─ models.py            # 매물 테이블·제약·인덱스
│  └─ repositories.py      # 매물 저장·조회·잠금·종류 잠금(advisory) 및 엔티티 변환
├─ trades/
│  ├─ models.py            # 거래 테이블·제약·인덱스
│  └─ repositories.py      # 거래 저장·내역 조회 및 엔티티 변환
└─ adapters/
   ├─ user_gateway.py      # Users 서비스 연결
   ├─ inventory_gateway.py # Inventory 서비스 연결, 예외 변환
   ├─ wallet_gateway.py    # Wallet 서비스 연결
   ├─ held_amount_reader.py# Wallet에 예약 금액 합계 제공
   └─ transaction.py       # commit·rollback
```

## 책임 경계

| 영역 | 책임 | 책임 아님 |
|---|---|---|
| listings | 매물 저장·조회, 행 잠금, 종류 잠금, ORM ↔ Listing 변환, 종류별 진행 매물 1개 제약 | 입찰·취소 규칙, 잔액 확인, 정산 순서 |
| trades | 신규 거래 저장, 내역·기간 내 낙찰 시각 조회, ORM ↔ Trade 변환, 매물당 거래 1건 제약 | 매물 상태 변경, 돈·아이템 이동, 입찰 제한 판단 |
| adapters | 다른 도메인이 공개한 서비스 호출, 계약 형식 변환, 예외 변환 | 업무 규칙, commit |

## Inventory 예외 변환

| 상황 | 인벤토리 예외 | 경매 예외 |
|---|---|---|
| 소유권 이전 중 낙찰자 탈퇴·행 없음 | `OwnerNotFoundError` | `SettlementNotPossibleError` (자동 유찰) |
| 아이템 누락·상태·소유권 불일치 (이전·해제) | `ItemNotFoundError`·`InvalidStateError`·`NotOwnerError` | `InventoryMismatchError` (500) |

변환할 때 원래 예외 유형과 관련 ID를 로그로 남긴다. Wallet 예외는 그대로 전달한다. Users의 회원 없음은 `None`(이름 조회는 생략)으로 바꿔 서비스가 판단하게 한다.

## 연결 규칙

- 모델은 공통 `database.Base`를 사용한다. database 모듈은 import할 때 엔진도 만들므로 DB 설정이 필요하다.
- Repository·Adapter는 외부에서 AsyncSession을 받는다. 세션을 직접 만들지 않으며, flush까지만 한다.
- 기존 매물 변경은 같은 트랜잭션에서 잠금 조회 → 도메인 변경 → 저장 순서로 한다.
- 대기열·마감 목록 조회는 후보 조회다. 실제 변경 전에 잠금 조회와 상태 재검사가 필요하다.
- 종류 잠금은 `pg_advisory_xact_lock(731402, item_definition_id)`이다. users는 731401을 쓴다.
- 다른 도메인의 모델은 import하지 않는다. 같은 auction 안의 `trades.listing_id`만 FK로 연결한다.
- 기존 테이블 변경은 `create_all`로 반영되지 않는다. 컬럼 추가는 마이그레이션이 필요하다.
  (`admin_cancelled_by`: `scripts/migrate-auction-admin-cancel.py`)

## 의존 방향

- infrastructure → domain 엔티티·Repository 인터페이스 허용
- infrastructure → 공통 database·SQLAlchemy 허용
- adapters → 다른 도메인의 application 서비스·DTO·예외 허용 (모델 import 금지)
- infrastructure → presentation import 금지

## 더 보기

- [경매 전체 안내](../README.md) · [도메인 역할과 경계](../domain/README.md)
- [매물 모델](listings/models.py) · [매물 Repository](listings/repositories.py)
- [거래 모델](trades/models.py) · [거래 Repository](trades/repositories.py)

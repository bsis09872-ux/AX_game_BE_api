# auction / infrastructure

auction 바운디드 컨텍스트(BC)의 infrastructure 계층이다. SQLAlchemy로 도메인의 저장·조회 계약을 구현하고 PostgreSQL 테이블 구조를 정의한다.

## 폴더 구조

```text
infrastructure/
├─ listings/
│  ├─ models.py         # 매물 테이블·제약·인덱스
│  └─ repositories.py   # 매물 저장·조회·잠금 및 엔티티 변환
├─ trades/
│  ├─ models.py         # 거래 테이블·제약·인덱스
│  └─ repositories.py   # 거래 저장·내역 조회 및 엔티티 변환
└─ README.md            # 인프라 책임과 연결 안내
```

## 책임 경계

| 영역 | 책임 | 책임 아님 |
|---|---|---|
| listings | 매물 저장·조회, 행 잠금, ORM ↔ Listing 변환, 종류별 진행 매물 중복 방지 제약 | 입찰·취소 규칙 판단, 잔액 확인, 정산 순서 |
| trades | 신규 거래 저장, 낙찰·판매 내역과 최근 낙찰 시각 조회, ORM ↔ Trade 변환, 매물당 거래 1건 제약 | 매물 상태 변경, 돈·아이템 이동, 입찰 제한 판단 |

## 왜 이렇게 나눴는지

- listings와 trades의 저장·조회 구현을 각 도메인 계약에 맞춰 분리한다.
- ORM 모델은 테이블 구조를, Repository는 쿼리와 엔티티 변환을 맡는다.
- 다른 도메인의 모델은 import하지 않고 ID 값만 저장한다. 같은 auction 내부의 trades.listing_id만 FK로 연결한다.

## 경계 밖과의 연결

- 모델은 공통 `database.Base`를 사용한다. 현재 database 모듈은 import 시 엔진도 생성하므로 DB 설정이 필요하다.
- Repository는 외부에서 AsyncSession과 page_size를 받는다. 세션을 직접 생성하지 않는다.
- save는 flush 후 엔티티를 반환한다. commit·rollback은 application의 유스케이스와 세션 관리 코드에서 처리한다.
- 기존 매물 변경은 같은 트랜잭션에서 잠금 조회 → 도메인 변경 → 저장 순서로 수행한다.
- 대기열·마감 목록은 후보 조회다. 실제 변경 전 잠금 조회와 상태 재검사가 필요하다.
- 테이블 생성 전에 두 모델을 앱 조립 위치에서 등록한다. 기존 테이블 변경은 마이그레이션으로 반영한다.

## 의존 방향

- infrastructure → domain 엔티티·Repository 인터페이스 허용
- infrastructure → 공통 database·SQLAlchemy 허용
- infrastructure → application / presentation / 다른 도메인 모델 import 금지

## 더 보기

- [도메인 역할과 경계](../domain/README.md)
- [매물 모델](listings/models.py) · [매물 Repository](listings/repositories.py)
- [거래 모델](trades/models.py) · [거래 Repository](trades/repositories.py)

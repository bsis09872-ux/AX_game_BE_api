# auction / application

매물 등록·입찰·취소, 마감 정산, 관리자 조회의 실행 순서를 조율한다.
업무 규칙은 domain에, DB와 다른 도메인 호출은 infrastructure(Repository·Adapter)에 맡긴다.

## 파일 역할

| 파일 | 역할 |
|---|---|
| `listings/service.py` | 매물 조회·등록·입찰·판매자 취소·관리자 강제 취소·관리자 전체 매물 조회 |
| `listings/queue.py` | 같은 종류의 다음 대기 매물 잠금 조회(FIFO). 정산·유찰·관리자 취소가 함께 쓴다 |
| `trades/service.py` | 내 낙찰·판매 내역, 입찰 제한 상태, 관리자 거래 조회 |
| `auction_service.py` | 마감 정산·유찰·자동 유찰·다음 매물 공개. 스케줄러가 호출한다 |
| `admin_queries.py`·`admin_dto.py` | 관리자 화면용 매물·거래 조회와 전달 형식 |
| `contract.py` | 다른 도메인에 요청하는 계약(Users·Inventory·Wallet·트랜잭션) |
| `dto.py` | 다른 도메인과 주고받는 데이터 형식 |

## 마감 정산 (`AuctionService.close_expired`)

매물 1건 = 트랜잭션 1개.
잠금 순서: 매물 → 아이템 종류(advisory) → 다음 대기 매물 → 아이템 → 사용자 → 지갑.

1. 마감된 BIDDING 매물을 잠그고 상태를 다시 확인한다.
2. 아이템 종류와 다음 대기 매물을 잠근다.
3. 입찰자가 있으면 정산: 아이템 이전 → 지갑 정산 → SOLD → Trade 저장 → 낙찰 제한 갱신.
   입찰자가 없으면 유찰: FAILED → 아이템 예약 해제.
4. 다음 대기 매물을 공개하고 commit한다.

| 실패 | 처리 |
|---|---|
| 낙찰자 탈퇴·행 없음 (`SettlementNotPossibleError`) | rollback 후 새 트랜잭션에서 자동 유찰 |
| 인벤토리·지갑 불일치, DB 오류 | rollback 후 다음 주기에 재시도 |

- 제한 중에 기존 입찰이 낙찰돼도 정산한다.
- [TO DO][V2] 운영자 확인 대상(인벤토리·지갑 불일치)을 식별·복구하는 방안을 정한다. (진행 전)

## 관리자 기능

- 권한은 서비스에서 `is_admin`으로 확인한다. 일반 사용자는 403.
- 강제 취소는 QUEUED·BIDDING만 가능하다. 처리한 관리자 ID와 `closed_at`만 기록한다.
- BIDDING 매물을 취소하면 같은 종류의 다음 대기 매물을 공개한다.

## 트랜잭션

- 변경 요청은 같은 세션에서 처리하고 마지막에 `tx.commit()`한다. 실패하면 commit하지 않고 예외를 올린다.
- 다른 도메인 예외는 import하지 않는다. 필요한 변환은 infrastructure Adapter가 한다.

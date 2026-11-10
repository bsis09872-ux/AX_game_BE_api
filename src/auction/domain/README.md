# auction / domain

auction 바운디드 컨텍스트(BC)의 domain 계층이다. 순수 Python으로 규칙을 정의하며 DB·FastAPI를 모른다.

## 폴더 구조

```text
domain/
├─ exceptions.py         # 경매 예외
├─ listings/
│  ├─ entities.py        # 매물 상태·입찰 규칙·마감 판단·취소
│  └─ repositories.py    # 매물 저장·조회·잠금 인터페이스
└─ trades/
   ├─ entities.py        # 낙찰 확정 기록
   ├─ repositories.py    # 거래 기록 저장·조회 인터페이스
   └─ policies.py        # 연속 낙찰 제한 계산
```

## 애그리거트 경계

| 애그리거트 | 책임 | 책임 아님 |
|---|---|---|
| Listing | 매물 상태 전이, 입찰 규칙, 마감 판단, 판매자·관리자 취소 | 잔액 확인, 연속 낙찰 제한, 재판매 제한, 정산 순서, 관리자 권한 확인 |
| Trade | 낙찰 확정 기록(불변), 내역의 근거, 연속 낙찰 제한 판단 재료 | 매물 상태 변경, 돈 이동 |

**매물 상태 전이**

- QUEUED → BIDDING → SOLD / FAILED
- QUEUED → CANCELLED (판매자·관리자)
- BIDDING → CANCELLED (관리자만)

## 예외

| 예외 | 응답 | 용도 |
|---|---|---|
| `AuctionEndedError` | 409 | 마감된 매물에 입찰 |
| `BidNotHigherError` | 409 | 현재 최고가 이하 입찰 |
| `BidBannedError` | 403 | 연속 낙찰 제한 중 입찰 |
| `InventoryMismatchError` | 500 | 매물과 인벤토리 아이템 상태 불일치 |
| `SettlementNotPossibleError` | 500 | 낙찰자 탈퇴·행 없음. 스케줄러의 자동 유찰 신호 |

## 왜 이렇게 나눴는지

- listings와 trades는 같은 사건인 낙찰의 앞뒤를 다루므로 같은 BC에 둔다.
- 생명주기가 달라 애그리거트는 분리한다. Trade는 Listing 객체를 보관하지 않고 listing_id로만 참조한다.
- wallet은 경매와 무관한 생명주기를 가지므로 별도 컨텍스트로 둔다.

## 경계 밖과의 연결

- 다른 도메인은 ID 값만 저장한다(FK 없음). seller_id·buyer_id·bidder_id는 auction의 역할 이름이다.
- 다른 도메인 연결 계약은 `application/contract.py`, 정산·마감 조율은 `application/auction_service.py`가 맡는다.
- 재판매 제한은 inventory 담당이다. auction은 에러만 전달한다.

## 의존 방향

- trades → listings 허용
- listings → trades 금지
- domain → application / infrastructure / presentation 금지

## 연속 낙찰 제한

- User는 횟수·종료 시각을 저장하고, Auction은 계산 규칙을 소유한다.
- 최근 30분 내 3회 낙찰 시 15분간 새 입찰 제한. 제한 중 추가 낙찰은 종료 시각을 연장하지 않는다.

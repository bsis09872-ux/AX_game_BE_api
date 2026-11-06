# auction / domain

auction 바운디드 컨텍스트(BC)의 domain 계층이다. 순수 Python으로 규칙을 정의하며 DB·FastAPI를 모른다.

## 폴더 구조

```text
 domain/
 ├─ listings/
 │  ├─ entities.py       # 매물 상태·입찰 규칙·마감 판단
 │  └─ repositories.py   # 매물 저장·조회 인터페이스
 ├─ trades/
 │  ├─ entities.py       # 낙찰 확정 기록
 │  ├─ repositories.py   # 거래 기록 저장·조회 인터페이스
 │  └─ policies.py       # 낙찰 기록 기반 연속 낙찰 제한 판단
 ├─ README.md           # 도메인 경계 안내
 └─ AUC08_RULES.md      # 연속 낙찰 제한 확정 규칙 (구현 예정)
```

## 애그리거트 경계

| 애그리거트 | 책임                                                                  | 책임 아님                                         |
| ---------- | --------------------------------------------------------------------- | ------------------------------------------------- |
| Listing    | 매물 상태(QUEUED → BIDDING → SOLD/FAILED, QUEUED → CANCELLED), 입찰 규칙, 마감 판단       | 잔액 확인, 연속 낙찰 제한, 재판매 제한, 정산 순서 |
| Trade      | 낙찰 확정 기록(불변), 낙찰·판매 내역의 근거, 연속 낙찰 제한 판단 재료 | 매물 상태 변경, 돈 이동                           |

## 왜 이렇게 나눴는지

- listings와 trades는 같은 사건인 낙찰의 앞뒤를 다루므로 같은 BC에 둔다.
- 생명주기가 달라 애그리거트는 분리한다. Trade는 Listing 객체를 보관하지 않고 listing_id로만 참조한다.
- wallet은 경매와 무관한 생명주기를 가지므로 별도 컨텍스트로 둔다.

## 경계 밖과의 연결

- 다른 도메인은 ID 값만 저장한다(FK 없음). seller_id/buyer_id/bidder_id는 auction의 역할 이름이다.
- [TO DO] 다른 도메인 연결 계약은 application/constructs.py에 정의한다. 아직 미구현이다.
- 재판매 제한은 inventory 담당이다. auction은 에러만 전달한다.
- [TO DO] 정산·마감 조율은 application/auction_service.py에 구현한다. 아직 미구현이다.

## 의존 방향

- trades → listings 허용
- listings → trades 금지
- domain → application / infrastructure / presentation 금지

## 연속 낙찰 제한

- [B 방식 확정 규칙](AUC08_RULES.md)을 따른다. 현재 policies.py는 이전 방식이며 교체가 필요하다.
- User는 횟수·종료 시각을 저장하고 Auction은 계산 규칙을 소유한다.

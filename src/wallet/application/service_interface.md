# 지갑(wallet)이 다른 도메인에 제공하는 기능

다른 도메인은 이 문서의 메서드만 사용한다. 지갑의 모델·테이블·infrastructure를 직접 import하지 않는다.

## 서비스 얻기

```python
from wallet.wiring import build_wallet_service

wallet_service = build_wallet_service(session)  # 호출자의 세션을 그대로 넘긴다
```

- 같은 세션을 넘기면 호출자의 트랜잭션에 함께 묶인다. 지갑은 **flush까지만** 하고 commit하지 않는다.
- **commit/rollback은 호출자가 한다.** 잔액 변경 로그는 지갑이 세션 이벤트로 처리한다.
  - commit 성공 → 로그가 남는다
  - rollback → 로그가 버려진다
  - 호출자가 `flush()`/`discard()`를 따로 부를 필요 없다.

## 경매(auction)가 쓰는 메서드

| 명세 | 호출 시점 | 메서드 | 반환 | 예외 (HTTP) |
| --- | --- | --- | --- | --- |
| WALL-07 입찰 금액 확인 | AUCT-01 입찰: 매물 FOR UPDATE + 경매 규칙 검사 후 | `check_bid_funds(*, bidder_id, amount, current_bidder_id, current_bid_amount)` | `BidFundsCheck(required_extra, available_before, available_after)` | `InsufficientBalanceError` (400), `WalletNotFoundError` (404, 없는 회원) |
| WALL-08 낙찰 정산 | AUCT-04 마감: 매물 FOR UPDATE + BIDDING·마감 확인 후, **입찰자가 있을 때만** | `settle_sale(*, buyer_id, seller_id, price)` | `SettlementAmounts(buyer_debit, seller_credit, fee)` | `BuyerBalanceShortError` (500, 데이터 불일치), `WalletNotFoundError` (404), `ValueError` (구매자=판매자) |

### WALL-07 `check_bid_funds`
- **검사만 한다.** 잔액은 바꾸지 않는다(예약 방식).
- 통과하면 `listings.current_bidder_id`, `current_bid_amount` 갱신은 경매가 한다.
- 예약 금액(held)은 "내가 최고 입찰자인 BIDDING 매물들의 입찰액 합계"로 지갑이 계산한다. **경매가 잔액·예약 합계를 따로 계산하지 않는다.**
- `current_bidder_id`, `current_bid_amount`는 매물의 현재 값이다. 둘 다 None이거나 둘 다 값이어야 한다.
  - 경매 규칙상 현재 최고 입찰자는 재입찰할 수 없으므로, 입찰자는 항상 "새 입찰자"다. 묶일 금액 = 입찰액 전액.
  - 따라서 `current_bidder_id=None, current_bid_amount=None`으로 넘겨도 결과가 같다.
- 입찰자 지갑만 잠근다(FOR UPDATE). 밀려나는 이전 입찰자 지갑은 잠그지 않는다(사용 가능 금액이 늘기만 하므로).

### WALL-08 `settle_sale`
- 구매자 `-price`, 판매자 `+(price - 수수료)`. 수수료는 현재 0.
- 두 지갑을 user_id 오름차순으로 잠근다(교차 정산 데드락 방지).
- 유찰(입찰자 없음)이면 호출하지 않는다. 예약 방식이라 돌려줄 돈이 없다.
- 거래 기록(trades), SOLD 처리, 아이템 이전, 구매자 낙찰 횟수(`users.update_limit`)는 경매가 한다.
- 이중 정산은 경매의 매물 잠금·상태 확인과 `trades.listing_id` UNIQUE가 막는다. 지갑 함수만으로는 막지 않는다.

### 경매 `WalletGateway` 연결 예시
경매 contract.py의 `has_balance` / `transfer` 이름을 그대로 두고 어댑터에서 연결할 수 있다.

```python
# auction/infrastructure/adapters/wallet_gateway.py
class WalletGatewayAdapter(WalletGateway):
    def __init__(self, wallet_service: WalletService) -> None:
        self._wallet = wallet_service

    async def has_balance(self, user_id: int, amount: int) -> bool:
        # 재입찰 금지 규칙 → 항상 새 입찰자. 부족하면 InsufficientBalanceError(400)가 그대로 올라간다.
        await self._wallet.check_bid_funds(
            bidder_id=user_id, amount=amount, current_bidder_id=None, current_bid_amount=None)
        return True

    async def transfer(self, from_user_id: int, to_user_id: int, amount: int) -> None:
        await self._wallet.settle_sale(buyer_id=from_user_id, seller_id=to_user_id, price=amount)

# auction/wiring.py
#   wallets=WalletGatewayAdapter(build_wallet_service(session)),
```

## 공통 규칙

### 지갑 지연 생성 (WALL-06)
- 지갑은 가입할 때가 아니라 **처음 필요할 때** 만든다(조회·입찰 확인·정산·충전). 초기 골드 `INITIAL_BALANCE` = 3,000.
- 여러 번·동시에 불려도 지급은 한 번뿐이다(`INSERT ... ON CONFLICT DO NOTHING`).
- 그래서 `check_bid_funds`/`settle_sale`이 호출자의 트랜잭션 안에서 지갑을 INSERT할 수 있다.
- 다른 도메인이 미리 만들어 두고 싶으면 `ensure_wallet(user_id)`를 부른다(이미 있으면 아무 일도 없다).

### 잠금 순서
- 경매 합의: **매물 → 아이템 → 사용자 → 지갑**. 여러 명이면 user_id 오름차순.
- 지갑은 마지막이다. 지갑 내부도 user_id 오름차순으로 만들고(ensure) 잠근다(lock).

### 예외
모두 `shared.core.exceptions`의 공통 분류를 상속하므로, 호출자는 변환하지 않고 그대로 올리면 공통 핸들러가 응답한다.

| 예외 | 분류 | HTTP | 언제 |
| --- | --- | --- | --- |
| `InsufficientBalanceError` | BusinessRuleError | 400 | 사용 가능 금액 부족 |
| `WalletNotFoundError` | NotFoundError | 404 | 없는 회원 |
| `InsufficientAuthorityError` | ForbiddenError | 403 | 관리자 아닌 충전 (지갑 API 전용) |
| `BuyerBalanceShortError` | AppError | 500 | 정산 시 구매자 잔액 < 낙찰가 (예약 규칙이 지켜지면 생기지 않는 데이터 불일치) |

## 지갑이 다른 도메인에 필요한 것 (application/contracts.py)

| 계약 | 제공 도메인 | 현재 구현 |
| --- | --- | --- |
| `RoleCheck.is_admin(user_id)` | users | `UserService.get_user(id).role` (infrastructure/role_checker.py) |
| `HeldAmountReader.held_amount(user_id)` | auction | **임시**: listings 테이블 직접 조회 (infrastructure/held_amount_reader.py). auction이 `sum_leading_bids`를 공개하면 교체 |

## 미정 (팀 결정 필요)
- 거래 수수료율 (현재 0, `domain/rules.py`의 `FEE_PERCENT`)
- 초기 지급액 (현재 3,000, `INITIAL_BALANCE`)
- 탈퇴 회원의 잔액·입찰 처리

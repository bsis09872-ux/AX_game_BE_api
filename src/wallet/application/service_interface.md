# WalletService 사용법

서비스 얻기 (호출자의 세션을 그대로 넘긴다):

```python
from wallet.wiring import build_wallet_service
wallet_service = build_wallet_service(session)
```

서비스는 commit하지 않는다. 잔액이 바뀐 결과에는 `balance_changes`가 있으니,
호출자가 **commit 성공 뒤에** `wallet.application.balance_log.log_balance_changes(result.balance_changes)`를 호출한다.

## 외부 API용 (라우터가 사용)

| 메서드 | 반환 | 던지는 예외 |
| --- | --- | --- |
| `get_my_wallet(user_id)` | `WalletView` | `WalletNotFoundError` |
| `list_my_trades(user_id, *, role, page, size)` | `TradePage` | 없음 |
| `get_trade_detail(user_id, trade_id)` | `TradeDetailView` | `TradeNotFoundError` (당사자가 아니어도 같은 404) |

## 다른 도메인이 호출하는 내부 함수

| 명세 | 호출하는 곳 | 메서드 | 반환 | 실패 |
| --- | --- | --- | --- | --- |
| WALL-06 | AUTH-01 가입 (user flush 직후) | `create_wallet(user_id)` | `CreatedWallet` | 지갑 중복 → IntegrityError (가입 롤백) |
| WALL-07 | AUCT-01 입찰 (매물 FOR UPDATE 후) | `check_bid_funds(*, bidder_id, amount, current_bidder_id, current_bid_amount)` | `BidFundsCheck` | `InsufficientBalanceError` 400, `WalletNotFoundError` |
| WALL-08 | AUCT-04 마감 (매물 FOR UPDATE 후) | `settle_sale(*, listing_id, seller_id, item_definition_id, buyer_id, price, now)` | `SettlementResult` 또는 유찰이면 `None` | `BuyerBalanceShortError` 500, 이중 정산 → IntegrityError |

- WALL-07은 검사만 한다. 통과하면 `listings.current_bidder_id`, `current_bid_amount` 갱신은 경매 쪽이 한다.
- WALL-08은 `trades` 1행 추가와 구매자·판매자 잔액 변경까지 한다. `SOLD` 처리와 아이템 이전은 경매 쪽이 한다.
- 구매자 `auction_purchase_count` +1은 어디서 할지 미정이라 아직 하지 않는다.

## 계산 기준

- held_amount: `SUM(current_bid_amount) WHERE current_bidder_id = :user_id AND status = 'BIDDING'` (마감 후 정산 전 포함). 없으면 0.
- 판매 내역: trades에 seller_id가 없으므로 `listings.seller_id`와 조인.
- 최신순: `completed_at DESC, id DESC`.
- 다른 도메인 테이블은 `infrastructure/external_tables.py`의 가벼운 참조로 읽는다. 해당 도메인의 조회 기능이 합의되면 교체한다.

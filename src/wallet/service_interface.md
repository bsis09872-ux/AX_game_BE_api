# 라우터가 기대하는 service 함수 (wallet/service.py)

| 함수 | 반환 | 던지는 예외 |
| --- | --- | --- |
| `get_my_wallet(session, *, user_id: int)` | `WalletResponse` | `WalletNotFoundError` |
| `list_my_trades(session, *, user_id: int, role: "buy"/"sell"/"all", page: PageParams)` | `PageResponse[TradeListItem]` | 없음 |
| `get_trade_detail(session, *, user_id: int, trade_id: int)` | `TradeDetailResponse` | `TradeNotFoundError` (당사자가 아니어도 같은 404) |

- held_amount: `SUM(current_bid_amount) WHERE current_bidder_id = :user_id AND status = 'BIDDING'` (마감 후 정산 전 포함). 없으면 0.
- 판매 내역: trades에 seller_id가 없으므로 `listings.seller_id`와 조인.
- 최신순: `completed_at DESC, id DESC`.
- 서비스는 commit하지 않는다 (조회 전용).

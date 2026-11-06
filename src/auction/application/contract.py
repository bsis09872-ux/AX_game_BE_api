# [외부 계약] 경매 서비스가 다른 도메인에 요청하는 기능의 이름·양식을 정의한다.
# 여기에는 인터페이스(Protocol/ABC)만 두고 구현은 각 도메인이 맡는다.
# 다른 도메인의 엔티티·ORM·코드를 import하지 않고, 경매 쪽이 정한 이름과 dto.py의 양식만 사용한다.
# 사용처: auction_service.py (마감 정산), listings/service.py (등록·입찰·취소), trades/service.py (참여 상태 조회)
#
# ── 요청 → users: AuctionUserGateway ─────────────────────────────────────
# [TO DO][요청 → users] async get_state(user_id: int) -> AuctionUserState | None
#         용도: 참여 상태 조회용 사용자 정보를 읽는다. 없으면 None, 조회만 하며 저장·commit하지 않는다.
#         실제 User 조회 기능을 Adapter로 호출하고 User 필드를 AuctionUserState로 변환한다.
#         낙찰 횟수는 참고 저장값이다. 최근 30분 유효 횟수는 Trade 기록으로 다시 계산한다.
#         입찰·정산의 경쟁 제어에는 아래 잠금 계약을 사용한다. 일반 조회만으로 입찰을 확정하지 않는다.
# [TO DO][요청 → users] get_for_update_many(user_ids: list[int]) -> dict[int, AuctionUserState]
#         용도: 정산하는 동안 구매자·판매자 상태가 동시에 바뀌지 않게 잠그고, 제한 계산용 횟수·blocked_until을 받는다.
# [TO DO][요청 → users] update_limit(user_id: int, purchase_count: int, blocked_until: datetime | None) -> None
#         용도: 낙찰 후 계산한 횟수·제한 종료 시각을 정산과 같은 트랜잭션에서 저장한다.
# [TO DO][요청 → users] get_display_names(user_ids: list[int]) -> dict[int, str]
#         용도: 거래 기록에 체결 당시 판매자·구매자 이름을 스냅샷으로 남긴다.
#
# ── 요청 → wallet: WalletGateway ─────────────────────────────────────────
# [TO DO][요청 → wallet] has_balance(user_id: int, amount: int) -> bool
#         용도: 어떤 자산도 바꾸기 전에 구매자 잔액이 낙찰가 이상인지 확인한다.
# [TO DO][요청 → wallet] transfer(from_user_id: int, to_user_id: int, amount: int) -> None
#         용도: 낙찰가를 구매자에서 판매자로 옮긴다. 변경은 호출 측 트랜잭션에서 확정한다.
#
# ── 요청 → inventory: InventoryGateway ───────────────────────────────────
# [TO DO][요청 → inventory] release(inventory_item_id: int, owner_id: int, listing_id: int, now: datetime) -> None
#         용도: 유찰 시 매물에 묶여 있던 아이템 예약을 해제해 판매자에게 돌려준다.
# [TO DO][요청 → inventory] transfer_reserved(inventory_item_id: int, from_user_id: int, to_user_id: int, listing_id: int, now: datetime) -> None
#         용도: 낙찰 시 매물에 묶여 있던 아이템을 구매자에게 넘긴다.
# [TO DO][요청 → inventory] get_summary(inventory_item_id: int) -> ItemSummary
#         용도: 거래 기록에 아이템 이름을 스냅샷으로 남긴다. ItemSummary 양식은 dto.py에 경매 쪽이 정의한다.
#
# ── 합의 → 전체: TransactionManager ──────────────────────────────────────
# [TO DO][합의 → 전체] commit() -> None / rollback() -> None
#         용도: 매물 1건의 정산(재화·아이템·사용자·매물·거래)을 한 번에 확정하거나 전부 되돌린다.
# [TO DO][합의 → 전체] 위 Gateway들과 경매 Repository가 같은 트랜잭션(세션)을 공유하도록 연결 방식을 정한다.
# [TO DO][합의 → 전체] 잠금 순서: 매물 → 사용자(id 오름차순) → 지갑. 입찰 처리도 같은 순서를 쓴다.
#
# ── 경매 내부 작업 (요청 이름 확정 후) ───────────────────────────────────
# [TO DO] 확정된 이름·양식으로 위 4개 인터페이스를 이 파일에 정의한다.
# [TO DO] 요청 중 이름·양식이 바뀌면 auction_service.py 상단 TODO와 호출부를 함께 맞춘다.

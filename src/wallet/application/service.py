"""지갑 유스케이스 (WALL-01, 04, 05, 06, 07, 08)

- 서비스는 commit하지 않는다. 라우터나 내부 함수를 호출한 쪽(AUCT-01, AUCT-04)이 commit한다.
- WALL-06 지연 생성: 지갑이 필요한 시점(조회·입찰 확인·정산·충전)에 없으면 ensure_wallet이 만든다.
  가입 흐름(auth)을 고치지 않고 지갑 안에서 처리하기 위한 방식이다.
- 잔액 변경은 logger(BalanceRecord 계약)에 쌓이고, 호출자의 commit이 성공하면 로그로 남고
  rollback되면 버려진다(구현체가 세션 이벤트로 처리). 호출자는 commit/rollback만 하면 된다.
- 금액 판단은 domain/rules.py가 하고, 여기서는 조회·잠금·저장 순서만 조율한다.
- 이 계층은 domain과 자기 계약(application/contracts.py)만 import한다.
  구현체(DB, 로그, users 조회, listings 조회)는 wiring이 생성자로 넣어 준다.
"""
from wallet.application.contracts import HeldAmountReader, RoleCheck
from wallet.application.dto import WalletView
from wallet.domain import rules
from wallet.domain.wallet import Wallet
from wallet.domain.service import BalanceRecord
from wallet.domain.repository import WalletRepository
from wallet.domain.exceptions import WalletNotFoundError, InsufficientAuthorityError

class WalletService:
    def __init__(
        self,
        roleCheck: RoleCheck,
        logger: BalanceRecord,
        wallet_repo: WalletRepository,
        held_reader: HeldAmountReader,
    ):
        self.roleCheck = roleCheck          # users: 관리자 여부
        self.logger = logger                # 잔액 변경 기록
        self.wallet_repo = wallet_repo      # wallets 테이블
        self.held_reader = held_reader      # auction: 입찰로 묶인 금액


    async def get_wallet(self, user_id) -> Wallet:
        wallet = await self.wallet_repo.get(user_id)
        if not wallet:
            raise WalletNotFoundError()

        return wallet

    async def ensure_wallet(self, user_id: int) -> None:
        """WALL-06 지연 생성: 지갑이 없으면 초기 골드로 만든다. 처음 만든 경우에만 INITIAL_GRANT 기록.

        여러 번 호출해도 지급은 한 번뿐이다. 회원이 없으면 WalletNotFoundError.
        commit은 호출자가 한다. 지급 로그는 commit이 성공하면 자동으로 남는다.
        """
        created = await self.wallet_repo.create_if_absent(user_id, rules.INITIAL_BALANCE)
        if created is not None:
            self.logger.logging(user_id, 0, created.balance.value, "INITIAL_GRANT")

    async def _ensure_wallets(self, user_ids: list[int]) -> None:
        # lock과 같은 user_id 오름차순으로 만들어 잠금 순서를 맞춘다
        for user_id in sorted(set(user_ids)):
            await self.ensure_wallet(user_id)

    async def get_my_wallet(self, user_id: int) -> WalletView:
        """WALL-01 내 지갑 조회: 총잔액 + 예약 합계 + 사용 가능 금액
        처음 조회면 지갑을 만들므로 호출자(라우터)가 commit한다."""
        await self.ensure_wallet(user_id)
        wallet = await self.get_wallet(user_id)
        held = await self.held_reader.held_amount(user_id)
        return WalletView(
            user_id=wallet.user_id,
            balance=wallet.balance.value,
            held_amount=held,
            available_balance=rules.available_balance(wallet.balance.value, held),
            updated_at=wallet.updated_at,
        )


    async def create_wallet(self, user_id: int) -> Wallet:
        """WALL-06 지갑 생성, 초기 골드 지급.

        AUTH-01 가입 트랜잭션 안에서 user flush 직후 호출한다. commit은 호출자가 하고,
        지급 로그는 commit이 성공하면 자동으로 남는다. (지금은 ensure_wallet 지연 생성을 주로 쓴다)
        같은 계정에 두 번 호출하면 PK 위반이 그대로 올라가 가입 전체가 롤백된다.
        """
        wallet = await self.wallet_repo.create(user_id, rules.INITIAL_BALANCE)
        self.logger.logging(user_id, 0, wallet.balance.value, "INITIAL_GRANT")
        return wallet

    async def check_bid_funds(
        self,
        *,
        bidder_id: int,
        amount: int,
        current_bidder_id: int | None,
        current_bid_amount: int | None,
    ) -> rules.BidFundsCheck:
        """WALL-07 입찰 가능 금액 확인 (예약 방식: 검사만, 잔액은 바꾸지 않는다)

        AUCT-01이 매물을 FOR UPDATE로 잠그고 경매 규칙을 검사한 뒤, 매물의 현재 입찰 정보를 넘긴다.
        입찰자 지갑을 잠가서 같은 사람의 동시 입찰이 예약 합계를 동시에 늘리지 못하게 한다.
        밀려나는 이전 입찰자 지갑은 잠그지 않는다(사용 가능 금액이 늘기만 하므로).
        통과하면 listings의 current_bidder_id·current_bid_amount 갱신은 경매 쪽이 한다.
        실제 차감은 낙찰 정산(WALL-08)에서 한다.
        """
        await self._ensure_wallets([bidder_id])
        locked = await self.wallet_repo.lock([bidder_id])
        wallet = locked.get(bidder_id)
        if wallet is None:
            raise WalletNotFoundError()

        extra = rules.required_extra(
            bidder_id=bidder_id,
            amount=amount,
            current_bidder_id=current_bidder_id,
            current_bid_amount=current_bid_amount,
        )
        # 잠금 뒤에 읽어야 다른 매물에 대한 내 동시 입찰 결과까지 반영된다
        held = await self.held_reader.held_amount(bidder_id)
        return rules.check_bid_funds(balance=wallet.balance.value, held_amount=held, extra=extra)

    async def settle_sale(self, *, buyer_id: int, seller_id: int, price: int) -> rules.SettlementAmounts:
        """WALL-08 낙찰 정산 중 지갑 부분: 구매자 차감, 판매자 지급.

        AUCT-04가 매물을 FOR UPDATE로 잠그고 BIDDING·마감 경과를 확인한 뒤 호출한다.
        유찰(입찰자 없음)이면 호출하지 않는다. 예약 방식이라 돌려줄 돈이 없다.
        trades 기록, SOLD 처리, 아이템 이전은 경매 쪽이 한다(담당 확정 전).
        commit은 호출자가 한다. 잔액 변경 로그는 commit이 성공하면 자동으로 남는다.
        """
        if buyer_id == seller_id:
            raise ValueError("판매자와 구매자가 같습니다.")

        await self._ensure_wallets([buyer_id, seller_id])
        # 두 지갑을 user_id 오름차순으로 잠가 교차 정산(A↔B) 데드락을 피한다
        locked = await self.wallet_repo.lock([buyer_id, seller_id])
        buyer, seller = locked.get(buyer_id), locked.get(seller_id)
        if buyer is None or seller is None:
            raise WalletNotFoundError()

        amounts = rules.settlement_amounts(price=price, buyer_balance=buyer.balance.value)
        buyer.subtract_balance(amounts.buyer_debit, self.logger, "PURCHASE_DEBIT")
        seller.add_balance(amounts.seller_credit, self.logger, "SALE_CREDIT")

        await self.wallet_repo.save(buyer_id, buyer.balance.value)
        await self.wallet_repo.save(seller_id, seller.balance.value)
        return amounts


    async def add_balance(self, actor_id: int, user_id: int, amount: int):
        """관리자 충전. actor_id(요청자)가 관리자가 아니면 403, user_id(대상)가 없는 회원이면 404."""
        if not await self.roleCheck.is_admin(actor_id):
            raise InsufficientAuthorityError()

        await self.ensure_wallet(user_id)  # 없는 회원이면 여기서 WalletNotFoundError(404)
        wallet = await self.get_wallet(user_id)
        wallet.add_balance(amount, self.logger)
        await self.wallet_repo.save(user_id, wallet.balance.value)

    async def subtract_balance(self, user_id: int, amount: int):
        wallet = await self.get_wallet(user_id)
        wallet.subtract_balance(amount, self.logger)
        await self.wallet_repo.save(user_id, wallet.balance.value)



# from datetime import datetime

# from wallet.application.balance_log import BalanceChange
# from wallet.application.dto import (
#     CreatedWallet,
#     SettlementResult,
#     TradeDetailView,
#     TradeListRow,
#     TradePage,
#     WalletView,
# )
# from wallet.domain import rules
# from wallet.domain.exceptions import TradeNotFoundError, WalletNotFoundError
# from wallet.domain.repository import RoleFilter, WalletRepository


# class WalletService:
#     def __init__(self, repository: WalletRepository):
#         self.repository = repository

#     # ---------- 외부 API ----------
#     async def get_my_wallet(self, user_id: int) -> WalletView:
#         """WALL-01 내 지갑 조회"""
#         wallet = await self.repository.get(user_id)
#         if wallet is None:
#             raise WalletNotFoundError()
#         held = await self.repository.held_amount(user_id)
#         return WalletView(
#             user_id=wallet.user_id,
#             balance=wallet.balance,
#             held_amount=held,
#             available_balance=rules.available_balance(wallet.balance, held),
#             updated_at=wallet.updated_at,
#         )

#     async def list_my_trades(
#         self, user_id: int, *, role: RoleFilter, page: int, size: int
#     ) -> TradePage:
#         """WALL-04 내 거래 내역 (최신순). 상대방은 이름만, ID는 내보내지 않는다."""
#         records, total = await self.repository.list_trades(
#             user_id, role, offset=(page - 1) * size, limit=size
#         )
#         items = []
#         for r in records:
#             my_role = r.role_of(user_id)
#             items.append(
#                 TradeListRow(
#                     trade_id=r.trade_id,
#                     role=my_role,
#                     listing_id=r.listing_id,
#                     item_name=r.item_name,
#                     counterpart_name=r.seller_name if my_role == "buy" else r.buyer_name,
#                     price=r.price,
#                     completed_at=r.completed_at,
#                 )
#             )
#         return TradePage(items=items, page=page, size=size, total=total)

#     async def get_trade_detail(self, user_id: int, trade_id: int) -> TradeDetailView:
#         """WALL-05 거래 상세. 당사자가 아니면 없는 거래와 똑같이 404"""
#         record = await self.repository.get_trade(trade_id)
#         my_role = None if record is None else record.role_of(user_id)
#         if record is None or my_role is None:
#             raise TradeNotFoundError()

#         if my_role == "buy":
#             change = -record.price
#         else:
#             # TODO: 수수료가 생기면 체결 당시 수수료를 저장해 두고 그 값을 써야 한다 (지금은 0)
#             change = record.price - rules.fee_for(record.price)

#         return TradeDetailView(
#             trade_id=record.trade_id,
#             listing_id=record.listing_id,
#             item_name=record.item_name,
#             seller_name=record.seller_name,
#             buyer_name=record.buyer_name,
#             price=record.price,
#             completed_at=record.completed_at,
#             my_role=my_role,
#             my_balance_change=change,
#         )

#     # ---------- 내부 함수 ----------
#     async def create_wallet(self, user_id: int) -> CreatedWallet:
#         """WALL-06 지갑 생성·초기 지급. AUTH-01 가입 트랜잭션 안에서 user flush 직후 호출.

#         같은 계정에 두 번 호출하면 PK 위반(IntegrityError)이 그대로 올라가 가입 전체가 롤백된다.
#         """
#         wallet = await self.repository.create(user_id, rules.INITIAL_BALANCE)
#         return CreatedWallet(
#             user_id=wallet.user_id,
#             balance=wallet.balance,
#             balance_changes=[
#                 BalanceChange("INITIAL_GRANT", user_id, balance_before=0, amount=wallet.balance)
#             ],
#         )

#     async def check_bid_funds(
#         self,
#         *,
#         bidder_id: int,
#         amount: int,
#         current_bidder_id: int | None,
#         current_bid_amount: int | None,
#     ) -> rules.BidFundsCheck:
#         """WALL-07 입찰 가능 금액 확인 (검사만, 저장 없음)

#         AUCT-01이 매물을 FOR UPDATE로 잠그고 경매 규칙을 검사한 뒤, 매물의 현재 입찰 정보를 넘긴다.
#         입찰자 지갑을 잠가서 같은 사람의 동시 입찰이 예약 합계를 동시에 늘리지 못하게 한다.
#         밀려나는 이전 입찰자 지갑은 잠그지 않는다(사용 가능 금액이 늘기만 하므로).
#         통과하면 listings의 current_bidder_id·current_bid_amount 갱신은 경매 쪽이 한다.
#         """
#         locked = await self.repository.lock([bidder_id])
#         wallet = locked.get(bidder_id)
#         if wallet is None:
#             raise WalletNotFoundError()

#         extra = rules.required_extra(
#             bidder_id=bidder_id,
#             amount=amount,
#             current_bidder_id=current_bidder_id,
#             current_bid_amount=current_bid_amount,
#         )
#         # 잠금 뒤에 읽어야 다른 매물에 대한 내 동시 입찰 결과까지 반영된다
#         held = await self.repository.held_amount(bidder_id)
#         return rules.check_bid_funds(balance=wallet.balance, held_amount=held, extra=extra)

#     async def settle_sale(
#         self,
#         *,
#         listing_id: int,
#         seller_id: int,
#         item_definition_id: int,
#         buyer_id: int | None,
#         price: int | None,
#         now: datetime,
#     ) -> SettlementResult | None:
#         """WALL-08 낙찰 정산. 입찰자가 없으면(유찰) 아무것도 하지 않고 None.

#         AUCT-04가 매물을 FOR UPDATE로 잠그고 BIDDING·마감 경과를 확인한 뒤,
#         매물의 seller_id, item_definition_id, current_bidder_id(=buyer_id),
#         current_bid_amount(=price)를 넘긴다. SOLD 처리와 아이템 이전은 경매 쪽이 한다.

#         TODO(회의): 구매자 auction_purchase_count +1을 여기서 할지 경매 쪽에서 할지 미정이라 하지 않는다.
#         """
#         if buyer_id is None:
#             return None
#         if price is None:
#             raise ValueError("입찰자가 있는데 입찰액이 없습니다.")

#         # 두 지갑을 user_id 오름차순으로 잠가 교차 정산(A↔B) 데드락을 피한다
#         locked = await self.repository.lock([buyer_id, seller_id])
#         buyer, seller = locked.get(buyer_id), locked.get(seller_id)
#         if buyer is None or seller is None:
#             raise WalletNotFoundError()

#         amounts = rules.settlement_amounts(price=price, buyer_balance=buyer.balance)

#         names = await self.repository.display_names([buyer_id, seller_id])
#         item_name = await self.repository.item_name(item_definition_id)
#         if item_name is None or buyer_id not in names or seller_id not in names:
#             raise ValueError("정산에 필요한 아이템·회원 정보를 찾을 수 없습니다.")

#         # 같은 매물을 두 번 정산하면 trades.listing_id UNIQUE 위반으로 여기서 실패한다
#         trade_id = await self.repository.insert_trade(
#             listing_id=listing_id,
#             buyer_id=buyer_id,
#             item_name=item_name,
#             seller_name=names[seller_id],
#             buyer_name=names[buyer_id],
#             price=price,
#             completed_at=now,
#         )
#         await self.repository.set_balance(buyer_id, buyer.balance - amounts.buyer_debit)
#         await self.repository.set_balance(seller_id, seller.balance + amounts.seller_credit)

#         return SettlementResult(
#             trade_id=trade_id,
#             buyer_id=buyer_id,
#             price=price,
#             balance_changes=[
#                 BalanceChange("PURCHASE_DEBIT", buyer_id, buyer.balance, -amounts.buyer_debit,
#                               listing_id=listing_id, trade_id=trade_id),
#                 BalanceChange("SALE_CREDIT", seller_id, seller.balance, amounts.seller_credit,
#                               listing_id=listing_id, trade_id=trade_id),
#             ],
#         )

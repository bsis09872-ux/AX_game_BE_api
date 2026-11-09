"""지갑 유스케이스 (WALL-01, 06, 07, 08, 관리자 충전)

- 거래 내역·상세(WALL-04, 05)는 거래(trades)를 경매가 맡기로 해서 지갑에 두지 않는다.

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
        처음 조회면 지갑을 만들므로 호출자(라우터)가 commit한다.

        잔액과 예약금은 같은 시점 값이어야 한다. 지갑을 먼저 잠그고(FOR UPDATE) 예약금을 읽는다.
        - 정산(settle_sale)은 같은 지갑을 잠그고 잔액과 매물 상태를 한 트랜잭션에서 바꾼다.
          그래서 정산 중이면 commit까지 기다렸다가 둘 다 정산 후 값으로 읽는다.
        - 다른 사람이 내 입찰을 밀어내면 예약금만 줄고 잔액은 그대로라 어긋나지 않는다.
        """
        await self.ensure_wallet(user_id)
        wallet = await self._lock_one(user_id)
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
        trades 기록, SOLD 처리, 아이템 이전은 경매 쪽이 한다.
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
        wallet = await self._lock_one(user_id)
        wallet.add_balance(amount, self.logger)
        await self.wallet_repo.save(user_id, wallet.balance.value)

    async def subtract_balance(self, user_id: int, amount: int):
        wallet = await self._lock_one(user_id)
        wallet.subtract_balance(amount, self.logger)
        await self.wallet_repo.save(user_id, wallet.balance.value)

    async def _lock_one(self, user_id: int) -> Wallet:
        # 읽고 → 계산하고 → 덮어쓰는 변경은 반드시 잠금 조회로 읽는다.
        # 잠금 없이 읽으면 동시에 커밋된 정산(settle_sale)의 변경을 덮어써 잃어버린다.
        wallet = (await self.wallet_repo.lock([user_id])).get(user_id)
        if wallet is None:
            raise WalletNotFoundError()
        return wallet

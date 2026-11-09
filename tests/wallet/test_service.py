"""wallet.application.service 단위 테스트

DB 대신 메모리 가짜 저장소를 넣어 서비스 흐름만 확인한다.
실행: 레포 최상위에서 `pytest tests/wallet` (src가 import 경로에 있어야 함)
"""
import asyncio
from datetime import datetime, timezone

import pytest

from wallet.application.service import WalletService
from wallet.domain import rules
from wallet.domain.exceptions import (
    BuyerBalanceShortError,
    InsufficientAuthorityError,
    InsufficientBalanceError,
    WalletNotFoundError,
)
from wallet.domain.wallet import Balance, Wallet
from wallet.infrastructure.balance_recoder import BalanceRecordImpl
from wallet.application.contracts import RoleCheck

NOW = datetime(2026, 11, 6, tzinfo=timezone.utc)


class FakeRepo:
    def __init__(self, held: int = 0):
        self.wallets: dict[int, int] = {}
        self.held = held
        self.unknown_users: set[int] = set()  # users 테이블에 없는 회원 흉내

    async def get(self, user_id):
        if user_id not in self.wallets:
            return None
        return Wallet(user_id, Balance(self.wallets[user_id]), NOW)

    async def save(self, user_id, balance):
        self.wallets[user_id] = balance
        return Wallet(user_id, Balance(balance), NOW)

    async def create(self, user_id, balance):
        if user_id in self.wallets:
            raise RuntimeError("PK 위반")  # 실제로는 IntegrityError
        self.wallets[user_id] = balance
        return Wallet(user_id, Balance(balance), NOW)

    async def create_if_absent(self, user_id, balance):
        if user_id in self.unknown_users:
            raise WalletNotFoundError()  # 실제로는 users FK 위반을 저장소가 404로 바꾼다
        if user_id in self.wallets:
            return None
        self.wallets[user_id] = balance
        return Wallet(user_id, Balance(balance), NOW)

    async def lock(self, user_ids):
        self.locked = list(user_ids)
        return {uid: Wallet(uid, Balance(self.wallets[uid]), NOW)
                for uid in sorted(user_ids) if uid in self.wallets}

    # HeldAmountReader 모양도 함께 맞춘다 (make_service에서 held_reader로도 끼운다)
    async def held_amount(self, user_id):
        return self.held


class FakeRoleCheck(RoleCheck):
    """users 없이 관리자 여부를 정해 두는 가짜 RoleCheck"""
    def __init__(self, admin_ids: set[int] | None = None):
        self.admin_ids = admin_ids or set()

    async def is_admin(self, user_id):
        return user_id in self.admin_ids


def make_service(repo: FakeRepo, admin_ids: set[int] | None = None) -> WalletService:
    return WalletService(
        roleCheck=FakeRoleCheck(admin_ids),
        logger=BalanceRecordImpl(),
        wallet_repo=repo,
        held_reader=repo,
    )


# ---------- WALL-06 지갑 생성 ----------

def test_create_wallet_grants_initial_balance():
    repo = FakeRepo()
    service = make_service(repo)

    wallet = asyncio.run(service.create_wallet(1))

    assert wallet.balance.value == rules.INITIAL_BALANCE == 3_000
    assert repo.wallets[1] == 3_000


def test_create_wallet_records_grant_log_until_flush():
    service = make_service(FakeRepo())

    asyncio.run(service.create_wallet(1))

    [change] = service.logger.pending
    assert (change.event_type, change.user_id, change.balance_before, change.amount) == (
        "INITIAL_GRANT", 1, 0, 3_000)


def test_create_wallet_twice_fails():
    service = make_service(FakeRepo())
    asyncio.run(service.create_wallet(1))

    with pytest.raises(RuntimeError):
        asyncio.run(service.create_wallet(1))


# ---------- WALL-01 내 지갑 조회 ----------

def test_get_my_wallet_shows_held_and_available():
    repo = FakeRepo(held=1_000)
    repo.wallets[1] = 3_000

    view = asyncio.run(make_service(repo).get_my_wallet(1))

    assert (view.balance, view.held_amount, view.available_balance) == (3_000, 1_000, 2_000)
    assert service_logs(repo) == []  # 이미 있던 지갑이면 지급 없음


def service_logs(repo):
    service = make_service(repo)
    asyncio.run(service.get_my_wallet(1))
    return [(c.event_type, c.user_id, c.amount) for c in service.logger.pending]


# ---------- WALL-06 지연 생성 ----------

def test_first_view_creates_wallet_with_initial_balance():
    repo = FakeRepo()
    service = make_service(repo)

    view = asyncio.run(service.get_my_wallet(1))

    assert view.balance == rules.INITIAL_BALANCE
    assert repo.wallets[1] == 3_000
    assert [(c.event_type, c.amount) for c in service.logger.pending] == [("INITIAL_GRANT", 3_000)]


def test_initial_grant_happens_only_once():
    repo = FakeRepo()
    service = make_service(repo)

    asyncio.run(service.get_my_wallet(1))
    asyncio.run(service.get_my_wallet(1))

    assert repo.wallets[1] == 3_000
    assert len(service.logger.pending) == 1


def test_ensure_wallet_for_unknown_user_fails():
    repo = FakeRepo()
    repo.unknown_users.add(9)

    with pytest.raises(WalletNotFoundError):
        asyncio.run(make_service(repo).get_my_wallet(9))
    assert 9 not in repo.wallets


# ---------- WALL-07 입찰 가능 금액 확인 ----------

def bid(service, **kw):
    return asyncio.run(service.check_bid_funds(**kw))


def test_first_bid_within_available_passes_and_keeps_balance():
    repo = FakeRepo(held=0)
    repo.wallets[1] = 3_000
    service = make_service(repo)

    result = bid(service, bidder_id=1, amount=1_000, current_bidder_id=None, current_bid_amount=None)

    assert (result.required_extra, result.available_before, result.available_after) == (1_000, 3_000, 2_000)
    assert repo.wallets[1] == 3_000  # 예약 방식: 잔액은 그대로
    assert repo.locked == [1]        # 입찰자 지갑만 잠금


def test_bid_over_available_fails():
    repo = FakeRepo(held=2_500)  # 다른 매물에 2,500 묶여 있음
    repo.wallets[1] = 3_000
    service = make_service(repo)

    with pytest.raises(InsufficientBalanceError):
        bid(service, bidder_id=1, amount=501, current_bidder_id=2, current_bid_amount=400)


def test_raise_own_bid_checks_only_difference():
    # 이 매물에 내가 1,000으로 최고 입찰자 → held에 이미 1,000 포함. 2,500으로 올리면 1,500만 더 필요
    repo = FakeRepo(held=1_000)
    repo.wallets[1] = 3_000
    service = make_service(repo)

    result = bid(service, bidder_id=1, amount=2_500, current_bidder_id=1, current_bid_amount=1_000)

    assert (result.required_extra, result.available_after) == (1_500, 500)


def test_bid_without_wallet_creates_it_first():
    repo = FakeRepo()
    service = make_service(repo)

    result = bid(service, bidder_id=9, amount=100, current_bidder_id=None, current_bid_amount=None)

    assert repo.wallets[9] == 3_000
    assert result.available_after == 2_900
    assert [c.event_type for c in service.logger.pending] == ["INITIAL_GRANT"]


def test_bid_by_unknown_user_fails():
    repo = FakeRepo()
    repo.unknown_users.add(9)

    with pytest.raises(WalletNotFoundError):
        bid(make_service(repo), bidder_id=9, amount=100, current_bidder_id=None, current_bid_amount=None)


# ---------- WALL-08 낙찰 정산 (지갑 부분) ----------

def settle(service, **kw):
    return asyncio.run(service.settle_sale(**kw))


def test_settle_moves_price_from_buyer_to_seller():
    repo = FakeRepo()
    repo.wallets.update({1: 3_000, 2: 500})
    service = make_service(repo)

    amounts = settle(service, buyer_id=1, seller_id=2, price=1_200)

    assert repo.wallets == {1: 1_800, 2: 1_700}
    assert (amounts.buyer_debit, amounts.seller_credit, amounts.fee) == (1_200, 1_200, 0)
    assert repo.locked == [1, 2]


def test_settle_logs_both_changes_until_flush():
    repo = FakeRepo()
    repo.wallets.update({1: 3_000, 2: 500})
    service = make_service(repo)

    settle(service, buyer_id=1, seller_id=2, price=1_200)

    changes = [(c.event_type, c.user_id, c.balance_before, c.amount) for c in service.logger.pending]
    assert changes == [("PURCHASE_DEBIT", 1, 3_000, -1_200), ("SALE_CREDIT", 2, 500, 1_200)]


def test_settle_buyer_short_is_data_mismatch():
    repo = FakeRepo()
    repo.wallets.update({1: 1_000, 2: 0})
    service = make_service(repo)

    with pytest.raises(BuyerBalanceShortError):
        settle(service, buyer_id=1, seller_id=2, price=1_001)
    assert repo.wallets == {1: 1_000, 2: 0}  # 아무것도 바뀌지 않음


def test_settle_creates_missing_seller_wallet():
    repo = FakeRepo()
    repo.wallets[1] = 3_000
    service = make_service(repo)

    settle(service, buyer_id=1, seller_id=2, price=100)

    assert repo.wallets == {1: 2_900, 2: 3_100}  # 판매자: 초기 3,000 + 판매 100
    events = [(c.event_type, c.user_id) for c in service.logger.pending]
    assert events == [("INITIAL_GRANT", 2), ("PURCHASE_DEBIT", 1), ("SALE_CREDIT", 2)]


def test_settle_unknown_user_fails():
    repo = FakeRepo()
    repo.wallets[1] = 3_000
    repo.unknown_users.add(2)

    with pytest.raises(WalletNotFoundError):
        settle(make_service(repo), buyer_id=1, seller_id=2, price=100)
    assert repo.wallets == {1: 3_000}


def test_settle_same_user_rejected():
    repo = FakeRepo()
    repo.wallets[1] = 3_000

    with pytest.raises(ValueError):
        settle(make_service(repo), buyer_id=1, seller_id=1, price=100)


# ---------- 관리자 충전 권한 ----------

def test_charge_by_non_admin_is_forbidden():
    from shared.core.exceptions import ForbiddenError

    repo = FakeRepo()
    repo.wallets[1] = 3_000

    with pytest.raises(InsufficientAuthorityError) as e:
        # 요청자 5(관리자 아님)가 회원 1에게 충전 시도
        asyncio.run(make_service(repo).add_balance(5, 1, 1_000))
    assert isinstance(e.value, ForbiddenError)  # 공통 핸들러가 403으로 응답
    assert repo.wallets[1] == 3_000


def test_charge_by_admin_adds_balance():
    repo = FakeRepo()
    repo.wallets[1] = 3_000
    service = make_service(repo, admin_ids={99})

    asyncio.run(service.add_balance(99, 1, 1_000))

    assert repo.wallets[1] == 4_000
    assert 99 not in repo.wallets  # 요청자(관리자)의 지갑은 건드리지 않는다


def test_charge_checks_actor_not_target():
    # 대상이 관리자여도 요청자가 관리자가 아니면 거절
    repo = FakeRepo()
    repo.wallets[99] = 3_000

    with pytest.raises(InsufficientAuthorityError):
        asyncio.run(make_service(repo, admin_ids={99}).add_balance(5, 99, 1_000))

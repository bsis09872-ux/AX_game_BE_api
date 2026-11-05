"""개별 아이템(InventoryItem) 테스트: 지급, 판매 예약, 반환, 소유권 이전, 이력"""

import unittest
from datetime import datetime, timedelta, timezone

from inventory.domain.enums import ItemEventType, ItemOrigin, ItemStatus
from inventory.domain.exceptions import (
    InvalidStateError,
    ItemRuleViolationError,
    NotOwnerError,
    ResaleNotAvailableError,
)
from inventory.domain.inventory_item import InventoryItem
from inventory.domain.item_definition import ItemDefinition

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
OWNER = 1
BUYER = 2
STRANGER = 3


def make_definition() -> ItemDefinition:
    return ItemDefinition(
        code="golden_carp", name="황금 잉어", category="FISH", rarity="RARE", start_price=500
    )


def make_item(owner_id=OWNER, origin=ItemOrigin.REWARD, now=NOW, actor_id=None) -> InventoryItem:
    return InventoryItem.grant(make_definition(), owner_id, origin, now, actor_id=actor_id)


def make_listed_item() -> InventoryItem:
    item = make_item()
    item.reserve_for_listing(OWNER, NOW)
    return item


def make_traded_item(trade_time=NOW) -> InventoryItem:
    """경매로 팔려 BUYER가 소유한 아이템(재판매 대기 시간이 걸려 있다)."""
    item = make_listed_item()
    item.transfer_to(BUYER, trade_time)
    return item


class GrantTest(unittest.TestCase):
    def test_grant_creates_an_owned_item(self):
        definition = make_definition()
        item = InventoryItem.grant(definition, OWNER, ItemOrigin.REWARD, NOW)
        self.assertIs(item.definition, definition)
        self.assertEqual(item.owner_id, OWNER)
        self.assertIs(item.status, ItemStatus.OWNED)
        self.assertIs(item.origin, ItemOrigin.REWARD)
        self.assertEqual(item.acquired_at, NOW)
        self.assertIsNone(item.resale_available_at)

    def test_only_seed_admin_grant_and_reward_are_allowed(self):
        for origin in (ItemOrigin.SEED, ItemOrigin.ADMIN_GRANT, ItemOrigin.REWARD):
            with self.subTest(origin=origin):
                self.assertIs(make_item(origin=origin).origin, origin)
        for origin in (ItemOrigin.TRADE, "REWARD", None):
            with self.subTest(origin=origin):
                with self.assertRaises(ItemRuleViolationError) as caught:
                    make_item(origin=origin)
                self.assertIn("origin", caught.exception.message)

    def test_owner_id_must_be_a_positive_integer(self):
        for owner_id in (0, -1, True, "1", None, 1.5):
            with self.subTest(owner_id=owner_id):
                with self.assertRaises(ItemRuleViolationError) as caught:
                    make_item(owner_id=owner_id)
                self.assertIn("owner_id", caught.exception.message)

    def test_definition_must_be_an_item_definition(self):
        for definition in (None, "golden_carp", {"code": "golden_carp"}):
            with self.subTest(definition=definition):
                with self.assertRaises(ItemRuleViolationError) as caught:
                    InventoryItem.grant(definition, OWNER, ItemOrigin.REWARD, NOW)
                self.assertIn("definition", caught.exception.message)

    def test_now_must_have_a_timezone(self):
        for now in (datetime(2026, 11, 5, 12, 0), "2026-11-05", None):
            with self.subTest(now=now):
                with self.assertRaises(ItemRuleViolationError) as caught:
                    make_item(now=now)
                self.assertIn("now", caught.exception.message)

    def test_grant_records_one_granted_event(self):
        item = make_item(actor_id=9)
        events = item.pop_events()
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertIs(event.event_type, ItemEventType.GRANTED)
        self.assertIsNone(event.from_owner_id)
        self.assertEqual(event.to_owner_id, OWNER)
        self.assertEqual(event.actor_id, 9)
        self.assertIsNone(event.listing_id)
        self.assertIsNone(event.trade_id)
        self.assertEqual(event.created_at, NOW)


class ReserveForListingTest(unittest.TestCase):
    def test_owner_can_reserve_an_owned_item(self):
        item = make_item()
        later = NOW + timedelta(hours=1)
        item.reserve_for_listing(OWNER, later, listing_id=30)
        self.assertIs(item.status, ItemStatus.LISTED)
        self.assertEqual(item.owner_id, OWNER)
        self.assertEqual(item.acquired_at, NOW)

    def test_reserve_records_a_listed_event(self):
        item = make_item()
        item.pop_events()
        later = NOW + timedelta(hours=1)
        item.reserve_for_listing(OWNER, later, listing_id=30)
        (event,) = item.pop_events()
        self.assertIs(event.event_type, ItemEventType.LISTED)
        self.assertEqual((event.from_owner_id, event.to_owner_id), (OWNER, OWNER))
        self.assertEqual(event.actor_id, OWNER)
        self.assertEqual(event.listing_id, 30)
        self.assertIsNone(event.trade_id)
        self.assertEqual(event.created_at, later)

    def test_listing_id_is_optional(self):
        item = make_item()
        item.reserve_for_listing(OWNER, NOW)
        self.assertIs(item.status, ItemStatus.LISTED)

    def test_non_owner_cannot_reserve(self):
        item = make_item()
        item.pop_events()
        with self.assertRaises(NotOwnerError):
            item.reserve_for_listing(STRANGER, NOW)
        self.assertIs(item.status, ItemStatus.OWNED)
        self.assertEqual(item.pop_events(), [])

    def test_already_listed_item_cannot_be_reserved_again(self):
        item = make_listed_item()
        with self.assertRaises(InvalidStateError):
            item.reserve_for_listing(OWNER, NOW)

    def test_owner_check_comes_before_the_state_check(self):
        item = make_listed_item()
        with self.assertRaises(NotOwnerError):
            item.reserve_for_listing(STRANGER, NOW)

    def test_granted_item_has_no_resale_limit(self):
        item = make_item()
        item.reserve_for_listing(OWNER, NOW)
        self.assertIs(item.status, ItemStatus.LISTED)

    def test_item_bought_at_auction_cannot_be_listed_before_the_waiting_time(self):
        item = make_traded_item()
        item.pop_events()
        for now in (NOW, NOW + timedelta(minutes=29, seconds=59)):
            with self.subTest(now=now):
                with self.assertRaises(ResaleNotAvailableError):
                    item.reserve_for_listing(BUYER, now)
        self.assertIs(item.status, ItemStatus.OWNED)
        self.assertEqual(item.pop_events(), [])

    def test_item_can_be_listed_exactly_when_the_waiting_time_ends(self):
        item = make_traded_item()
        item.reserve_for_listing(BUYER, NOW + timedelta(minutes=30))
        self.assertIs(item.status, ItemStatus.LISTED)

    def test_resale_error_message_includes_the_available_time(self):
        item = make_traded_item()
        with self.assertRaises(ResaleNotAvailableError) as caught:
            item.reserve_for_listing(BUYER, NOW)
        self.assertIn(item.resale_available_at.isoformat(), caught.exception.message)

    def test_now_must_have_a_timezone(self):
        item = make_item()
        with self.assertRaises(ItemRuleViolationError):
            item.reserve_for_listing(OWNER, datetime(2026, 11, 5, 12, 0))
        self.assertIs(item.status, ItemStatus.OWNED)


class ReleaseFromListingTest(unittest.TestCase):
    def test_owner_gets_the_item_back_without_changing_acquired_at(self):
        item = make_listed_item()
        later = NOW + timedelta(hours=2)
        item.release_from_listing(OWNER, later, listing_id=30)
        self.assertIs(item.status, ItemStatus.OWNED)
        self.assertEqual(item.owner_id, OWNER)
        self.assertEqual(item.acquired_at, NOW)

    def test_release_records_an_unlisted_event(self):
        item = make_listed_item()
        item.pop_events()
        later = NOW + timedelta(hours=2)
        item.release_from_listing(OWNER, later, listing_id=30)
        (event,) = item.pop_events()
        self.assertIs(event.event_type, ItemEventType.UNLISTED)
        self.assertEqual((event.from_owner_id, event.to_owner_id), (OWNER, OWNER))
        self.assertEqual(event.actor_id, OWNER)
        self.assertEqual(event.listing_id, 30)
        self.assertEqual(event.created_at, later)

    def test_owned_item_cannot_be_released(self):
        item = make_item()
        with self.assertRaises(InvalidStateError):
            item.release_from_listing(OWNER, NOW)

    def test_non_owner_cannot_release(self):
        item = make_listed_item()
        item.pop_events()
        with self.assertRaises(NotOwnerError):
            item.release_from_listing(STRANGER, NOW)
        self.assertIs(item.status, ItemStatus.LISTED)
        self.assertEqual(item.pop_events(), [])


class TransferToTest(unittest.TestCase):
    def test_transfer_changes_owner_and_resets_acquisition_info(self):
        item = make_listed_item()
        later = NOW + timedelta(hours=3)
        item.transfer_to(BUYER, later, listing_id=30, trade_id=40)
        self.assertEqual(item.owner_id, BUYER)
        self.assertIs(item.status, ItemStatus.OWNED)
        self.assertEqual(item.acquired_at, later)
        self.assertIs(item.origin, ItemOrigin.TRADE)
        self.assertEqual(item.resale_available_at, later + timedelta(minutes=30))

    def test_waiting_time_can_be_changed(self):
        item = make_listed_item()
        item.transfer_to(BUYER, NOW, resale_delay=timedelta(minutes=5))
        self.assertEqual(item.resale_available_at, NOW + timedelta(minutes=5))

    def test_transfer_records_a_transferred_event(self):
        item = make_listed_item()
        item.pop_events()
        later = NOW + timedelta(hours=3)
        item.transfer_to(BUYER, later, listing_id=30, trade_id=40)
        (event,) = item.pop_events()
        self.assertIs(event.event_type, ItemEventType.TRANSFERRED)
        self.assertEqual((event.from_owner_id, event.to_owner_id), (OWNER, BUYER))
        self.assertIsNone(event.actor_id)
        self.assertEqual((event.listing_id, event.trade_id), (30, 40))
        self.assertEqual(event.created_at, later)

    def test_only_a_listed_item_can_be_transferred(self):
        item = make_item()
        with self.assertRaises(InvalidStateError):
            item.transfer_to(BUYER, NOW)

    def test_new_owner_must_differ_from_the_current_owner(self):
        item = make_listed_item()
        item.pop_events()
        with self.assertRaises(InvalidStateError):
            item.transfer_to(OWNER, NOW)
        self.assertIs(item.status, ItemStatus.LISTED)
        self.assertEqual(item.pop_events(), [])

    def test_new_owner_id_must_be_a_positive_integer(self):
        for new_owner_id in (0, -1, True, "2", None):
            with self.subTest(new_owner_id=new_owner_id):
                item = make_listed_item()
                with self.assertRaises(ItemRuleViolationError) as caught:
                    item.transfer_to(new_owner_id, NOW)
                self.assertIn("new_owner_id", caught.exception.message)
                self.assertEqual(item.owner_id, OWNER)

    def test_previous_owner_can_no_longer_act(self):
        item = make_traded_item()
        with self.assertRaises(NotOwnerError):
            item.reserve_for_listing(OWNER, NOW + timedelta(hours=1))


class PopEventsTest(unittest.TestCase):
    def test_pop_events_returns_the_events_and_empties_the_list(self):
        item = make_item()
        self.assertEqual(len(item.pop_events()), 1)
        self.assertEqual(item.pop_events(), [])

    def test_events_are_kept_in_order(self):
        item = make_item()
        item.reserve_for_listing(OWNER, NOW + timedelta(minutes=1))
        item.release_from_listing(OWNER, NOW + timedelta(minutes=2))
        item.reserve_for_listing(OWNER, NOW + timedelta(minutes=3))
        item.transfer_to(BUYER, NOW + timedelta(minutes=4))
        types = [event.event_type for event in item.pop_events()]
        self.assertEqual(
            types,
            [
                ItemEventType.GRANTED,
                ItemEventType.LISTED,
                ItemEventType.UNLISTED,
                ItemEventType.LISTED,
                ItemEventType.TRANSFERRED,
            ],
        )

    def test_a_sold_item_can_be_resold_after_the_waiting_time(self):
        item = make_traded_item()
        item.reserve_for_listing(BUYER, NOW + timedelta(minutes=30))
        item.transfer_to(STRANGER, NOW + timedelta(minutes=31))
        self.assertEqual(item.owner_id, STRANGER)
        events = item.pop_events()
        self.assertEqual(events[-1].from_owner_id, BUYER)
        self.assertEqual(events[-1].to_owner_id, STRANGER)


if __name__ == "__main__":
    unittest.main()

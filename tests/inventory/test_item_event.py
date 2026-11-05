"""아이템 이력(ItemEvent) 테스트: 값 객체이므로 만든 뒤 바꿀 수 없다"""

import unittest
from datetime import datetime, timezone

from inventory.domain.enums import ItemEventType
from inventory.domain.item_event import ItemEvent

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)


def make_event(**overrides) -> ItemEvent:
    values = {
        "event_type": ItemEventType.TRANSFERRED,
        "from_owner_id": 1,
        "to_owner_id": 2,
        "created_at": NOW,
    }
    values.update(overrides)
    return ItemEvent(**values)


class ItemEventTest(unittest.TestCase):
    def test_required_values_are_stored(self):
        event = make_event()
        self.assertIs(event.event_type, ItemEventType.TRANSFERRED)
        self.assertEqual(event.from_owner_id, 1)
        self.assertEqual(event.to_owner_id, 2)
        self.assertEqual(event.created_at, NOW)

    def test_optional_values_default_to_none(self):
        event = make_event()
        self.assertIsNone(event.actor_id)
        self.assertIsNone(event.listing_id)
        self.assertIsNone(event.trade_id)

    def test_optional_values_can_be_given(self):
        event = make_event(actor_id=9, listing_id=30, trade_id=40)
        self.assertEqual((event.actor_id, event.listing_id, event.trade_id), (9, 30, 40))

    def test_owner_ids_can_be_none(self):
        # 지급(GRANTED)은 이전 소유자가 없다
        event = make_event(event_type=ItemEventType.GRANTED, from_owner_id=None, to_owner_id=1)
        self.assertIsNone(event.from_owner_id)

    def test_event_cannot_be_modified(self):
        event = make_event()
        with self.assertRaises(AttributeError):
            event.to_owner_id = 3
        with self.assertRaises(AttributeError):
            event.event_type = ItemEventType.GRANTED

    def test_events_with_the_same_values_are_equal(self):
        self.assertEqual(make_event(), make_event())
        self.assertNotEqual(make_event(), make_event(to_owner_id=3))


if __name__ == "__main__":
    unittest.main()

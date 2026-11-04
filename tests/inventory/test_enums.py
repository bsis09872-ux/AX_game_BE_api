"""분류값(Enum) 테스트: 허용값이 설계 문서와 같은지, 이름과 값이 같은지"""

import unittest

from inventory.domain.enums import (
    ItemCategory,
    ItemEventType,
    ItemOrigin,
    ItemRarity,
    ItemStatus,
)

EXPECTED_VALUES = {
    ItemCategory: {"FISH", "GEM", "MISC"},
    ItemRarity: {"COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY"},
    ItemStatus: {"OWNED", "LISTED"},
    ItemOrigin: {"SEED", "ADMIN_GRANT", "REWARD", "TRADE"},
    ItemEventType: {"GRANTED", "LISTED", "UNLISTED", "TRANSFERRED"},
}


class EnumValuesTest(unittest.TestCase):
    def test_allowed_values_match_the_design(self):
        for enum_class, expected in EXPECTED_VALUES.items():
            with self.subTest(enum=enum_class.__name__):
                self.assertEqual({member.value for member in enum_class}, expected)

    def test_member_name_equals_value(self):
        for enum_class in EXPECTED_VALUES:
            for member in enum_class:
                with self.subTest(member=f"{enum_class.__name__}.{member.name}"):
                    self.assertEqual(member.name, member.value)

    def test_values_are_strings(self):
        for enum_class in EXPECTED_VALUES:
            for member in enum_class:
                with self.subTest(member=f"{enum_class.__name__}.{member.name}"):
                    self.assertIsInstance(member.value, str)

    def test_lookup_by_value_returns_the_member(self):
        self.assertIs(ItemStatus("OWNED"), ItemStatus.OWNED)
        self.assertIs(ItemOrigin("TRADE"), ItemOrigin.TRADE)

    def test_unknown_value_is_rejected(self):
        with self.assertRaises(ValueError):
            ItemCategory("PET")
        with self.assertRaises(ValueError):
            ItemRarity("owned")


if __name__ == "__main__":
    unittest.main()

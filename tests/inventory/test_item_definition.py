"""아이템 카탈로그(ItemDefinition) 테스트: 값 검증 규칙, 기본값, 이름·카테고리 불변, 수정"""

import unittest

from inventory.domain.enums import ItemCategory, ItemRarity
from inventory.domain.exceptions import DefinitionImmutableFieldError, ItemRuleViolationError
from inventory.domain.item_definition import ItemDefinition


def make_definition(**overrides) -> ItemDefinition:
    values = {
        "code": "golden_carp",
        "name": "황금 잉어",
        "category": "FISH",
        "rarity": "RARE",
        "start_price": 500,
    }
    values.update(overrides)
    return ItemDefinition(**values)


class ItemDefinitionCreationTest(unittest.TestCase):
    def test_valid_values_are_stored_with_defaults(self):
        definition = make_definition()
        self.assertEqual(definition.code, "golden_carp")
        self.assertEqual(definition.name, "황금 잉어")
        self.assertEqual(definition.start_price, 500)
        self.assertEqual(definition.description, "")
        self.assertEqual(definition.icon, "default")
        self.assertEqual(definition.weight, 10)
        self.assertIs(definition.fishable, True)

    def test_category_and_rarity_become_enum_members(self):
        definition = make_definition(category="GEM", rarity="EPIC")
        self.assertIs(definition.category, ItemCategory.GEM)
        self.assertIs(definition.rarity, ItemRarity.EPIC)

    def test_enum_members_are_accepted_too(self):
        definition = make_definition(category=ItemCategory.MISC, rarity=ItemRarity.COMMON)
        self.assertIs(definition.category, ItemCategory.MISC)
        self.assertIs(definition.rarity, ItemRarity.COMMON)

    def test_code_must_match_the_pattern(self):
        invalid_codes = ["Fish", "ab", "1fish", "bad-code", "", "한글코드", "a" * 51, "has space"]
        for code in invalid_codes:
            with self.subTest(code=code):
                with self.assertRaises(ItemRuleViolationError):
                    make_definition(code=code)

    def test_code_length_boundaries_are_allowed(self):
        for code in ("abc", "a" + "b" * 49):
            with self.subTest(length=len(code)):
                self.assertEqual(make_definition(code=code).code, code)

    def test_name_is_trimmed_and_must_have_1_to_100_characters(self):
        self.assertEqual(make_definition(name="  붕어  ").name, "붕어")
        self.assertEqual(len(make_definition(name="a" * 100).name), 100)
        for name in ("", "   ", "a" * 101, None, 5):
            with self.subTest(name=name):
                with self.assertRaises(ItemRuleViolationError):
                    make_definition(name=name)

    def test_unknown_category_or_rarity_is_rejected(self):
        for field, value in (("category", "PET"), ("category", "fish"), ("rarity", "MYTHIC"), ("rarity", None)):
            with self.subTest(field=field, value=value):
                with self.assertRaises(ItemRuleViolationError):
                    make_definition(**{field: value})

    def test_start_price_must_be_a_positive_integer(self):
        for price in (0, -1, 1.5, "100", True, None):
            with self.subTest(price=price):
                with self.assertRaises(ItemRuleViolationError):
                    make_definition(start_price=price)
        self.assertEqual(make_definition(start_price=1).start_price, 1)

    def test_weight_must_be_a_non_negative_integer(self):
        for weight in (-1, 1.5, "10", True, None):
            with self.subTest(weight=weight):
                with self.assertRaises(ItemRuleViolationError):
                    make_definition(weight=weight)
        self.assertEqual(make_definition(weight=0).weight, 0)

    def test_icon_must_have_1_to_50_characters(self):
        for icon in ("", "a" * 51, None, 5):
            with self.subTest(icon=icon):
                with self.assertRaises(ItemRuleViolationError):
                    make_definition(icon=icon)
        self.assertEqual(len(make_definition(icon="a" * 50).icon), 50)

    def test_fishable_must_be_a_real_boolean(self):
        for fishable in (1, 0, "true", None):
            with self.subTest(fishable=fishable):
                with self.assertRaises(ItemRuleViolationError):
                    make_definition(fishable=fishable)
        self.assertIs(make_definition(fishable=False).fishable, False)

    def test_error_message_names_the_bad_field(self):
        bad_values = {
            "code": "Bad",
            "name": "",
            "category": "PET",
            "rarity": "MYTHIC",
            "start_price": 0,
            "weight": -1,
            "icon": "",
            "fishable": "yes",
        }
        for field, value in bad_values.items():
            with self.subTest(field=field):
                with self.assertRaises(ItemRuleViolationError) as caught:
                    make_definition(**{field: value})
                self.assertIn(field, caught.exception.message)


class ItemDefinitionUpdateTest(unittest.TestCase):
    def test_update_changes_only_the_given_fields(self):
        definition = make_definition()
        definition.update(weight=3, start_price=900, icon="carp", description="반짝이는 잉어", fishable=False)
        self.assertEqual(definition.weight, 3)
        self.assertEqual(definition.start_price, 900)
        self.assertEqual(definition.icon, "carp")
        self.assertEqual(definition.description, "반짝이는 잉어")
        self.assertIs(definition.fishable, False)
        self.assertEqual(definition.code, "golden_carp")
        self.assertEqual(definition.name, "황금 잉어")

    def test_update_without_arguments_changes_nothing(self):
        definition = make_definition()
        definition.update()
        self.assertEqual(definition.weight, 10)
        self.assertEqual(definition.start_price, 500)

    def test_update_applies_the_same_value_rules(self):
        for field, value in (("start_price", 0), ("weight", -1), ("icon", ""), ("fishable", "yes")):
            with self.subTest(field=field):
                definition = make_definition()
                with self.assertRaises(ItemRuleViolationError):
                    definition.update(**{field: value})

    def test_failed_update_changes_nothing(self):
        definition = make_definition()
        with self.assertRaises(ItemRuleViolationError):
            definition.update(weight=5, start_price=0)
        self.assertEqual(definition.weight, 10)
        self.assertEqual(definition.start_price, 500)

    def test_update_rejects_name_or_category_even_with_the_same_value(self):
        for field, value in (("name", "새 이름"), ("name", "황금 잉어"), ("category", "GEM"), ("category", "FISH")):
            with self.subTest(field=field, value=value):
                definition = make_definition()
                with self.assertRaises(DefinitionImmutableFieldError):
                    definition.update(**{field: value})
                self.assertEqual(definition.name, "황금 잉어")
                self.assertIs(definition.category, ItemCategory.FISH)

    def test_update_with_immutable_field_changes_nothing_else(self):
        definition = make_definition()
        with self.assertRaises(DefinitionImmutableFieldError):
            definition.update(name="새 이름", weight=3)
        self.assertEqual(definition.weight, 10)

    def test_name_and_category_cannot_be_assigned_directly(self):
        definition = make_definition()
        with self.assertRaises(AttributeError):
            definition.name = "새 이름"
        with self.assertRaises(AttributeError):
            definition.category = ItemCategory.GEM


if __name__ == "__main__":
    unittest.main()

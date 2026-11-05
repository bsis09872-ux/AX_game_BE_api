"""인벤토리 테이블 모델 테스트: DB 제약(CHECK, FK, UNIQUE)이 설계 문서(db-schema.md)와 같은지 진짜 PostgreSQL로 확인한다

- 테스트마다 전용 스키마(u05_test)를 만들고 그 안에서만 테이블을 만들고 지운다. 개발용 테이블은 건드리지 않는다
- 환경 변수 DATABASE_URL(또는 루트 .env)이 없으면 건너뛴다
- database.py와 모델은 import하는 순간 DATABASE_URL을 요구해서 테스트 안에서 import한다
"""

import os
import unittest
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import delete, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

SCHEMA = "u05_test"
NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)


def definition_values(**overrides):
    values = {
        "code": "golden_carp",
        "name": "황금 잉어",
        "category": "FISH",
        "rarity": "RARE",
        "start_price": 500,
    }
    values.update(overrides)
    return values


def item_values(definition_id, **overrides):
    values = {
        "item_definition_id": definition_id,
        "owner_id": 1,
        "origin": "REWARD",
        "acquired_at": NOW,
    }
    values.update(overrides)
    return values


def event_values(item_id, **overrides):
    values = {
        "item_id": item_id,
        "event_type": "GRANTED",
        "from_owner_id": None,
        "to_owner_id": 1,
    }
    values.update(overrides)
    return values


@unittest.skipUnless(os.environ.get("DATABASE_URL"), "DATABASE_URL이 없어 모델 테스트를 건너뛴다")
class InventoryModelsTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import database
        from inventory.infrastructure import models

        self.engine = database.engine
        self.definitions = models.ItemDefinitionModel.__table__
        self.items = models.InventoryItemModel.__table__
        self.events = models.ItemEventModel.__table__
        # 테스트마다 이벤트 루프가 달라서 남은 연결을 닫고 새로 시작한다
        await self.engine.dispose()
        async with self.engine.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
            await connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
            scoped = await connection.execution_options(schema_translate_map={None: SCHEMA})
            await scoped.run_sync(
                lambda sync_connection: database.Base.metadata.create_all(
                    sync_connection, tables=[self.definitions, self.items, self.events]
                )
            )

    async def asyncTearDown(self):
        async with self.engine.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        await self.engine.dispose()

    # ----- 도우미: 전용 스키마 안에서 실행한다 -----
    async def run_statement(self, statement, fetch=None):
        async with self.engine.begin() as connection:
            scoped = await connection.execution_options(schema_translate_map={None: SCHEMA})
            result = await scoped.execute(statement)
            if fetch == "all":
                return result.all()
            if fetch == "one":
                return result.one()
            if fetch == "scalar":
                return result.scalar_one()
            return None

    async def insert(self, table, values) -> int:
        statement = table.insert().values(**values).returning(table.c.id)
        return await self.run_statement(statement, fetch="scalar")

    async def assert_rejected(self, table, values):
        # 제약 위반(IntegrityError)이나 길이 초과(DataError) 모두 DB가 거절한 것이다
        with self.assertRaises(DBAPIError):
            await self.insert(table, values)

    async def make_definition(self, **overrides) -> int:
        return await self.insert(self.definitions, definition_values(**overrides))

    async def make_item(self, **overrides) -> int:
        definition_id = await self.make_definition()
        return await self.insert(self.items, item_values(definition_id, **overrides))

    # ----- 테이블과 인덱스 -----
    async def test_the_three_tables_are_created(self):
        rows = await self.run_statement(
            text(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{SCHEMA}'"),
            fetch="all",
        )
        self.assertEqual(
            {row[0] for row in rows}, {"item_definitions", "inventory_items", "item_events"}
        )

    async def test_the_indexes_from_the_design_exist(self):
        rows = await self.run_statement(
            text(f"SELECT indexname FROM pg_indexes WHERE schemaname = '{SCHEMA}'"), fetch="all"
        )
        names = {row[0] for row in rows}
        for expected in (
            "ix_inventory_items_owner_status",
            "ix_inventory_items_definition",
            "ix_item_events_item_created",
        ):
            with self.subTest(index=expected):
                self.assertIn(expected, names)

    # ----- item_definitions -----
    async def test_definition_defaults_are_filled_by_the_database(self):
        definition_id = await self.make_definition()
        row = await self.run_statement(
            select(self.definitions).where(self.definitions.c.id == definition_id), fetch="one"
        )
        self.assertEqual(row.description, "")
        self.assertEqual(row.icon, "default")
        self.assertEqual(row.weight, 10)
        self.assertIs(row.fishable, True)
        self.assertIsNotNone(row.created_at.tzinfo)

    async def test_definition_code_must_be_unique(self):
        await self.make_definition()
        await self.assert_rejected(self.definitions, definition_values(name="다른 이름"))

    async def test_definition_code_format_is_checked(self):
        for code in ("Fish", "ab", "1fish", "bad-code", "a" * 51, ""):
            with self.subTest(code=code):
                await self.assert_rejected(self.definitions, definition_values(code=code))

    async def test_definition_code_length_boundaries_are_allowed(self):
        for code in ("abc", "a" + "b" * 49):
            with self.subTest(length=len(code)):
                await self.insert(self.definitions, definition_values(code=code))

    async def test_definition_category_and_rarity_are_checked(self):
        for field, value in (("category", "PET"), ("category", "fish"), ("rarity", "MYTHIC")):
            with self.subTest(field=field, value=value):
                await self.assert_rejected(self.definitions, definition_values(**{field: value}))

    async def test_definition_numbers_are_checked(self):
        for field, value in (("weight", -1), ("start_price", 0), ("start_price", -5)):
            with self.subTest(field=field, value=value):
                await self.assert_rejected(self.definitions, definition_values(**{field: value}))
        await self.insert(self.definitions, definition_values(code="zero_weight", weight=0))

    async def test_definition_required_columns_cannot_be_null(self):
        for field in ("code", "name", "category", "rarity", "start_price"):
            with self.subTest(field=field):
                await self.assert_rejected(self.definitions, definition_values(**{field: None}))

    # ----- inventory_items -----
    async def test_item_defaults_are_filled_by_the_database(self):
        item_id = await self.make_item()
        row = await self.run_statement(
            select(self.items).where(self.items.c.id == item_id), fetch="one"
        )
        self.assertEqual(row.status, "OWNED")
        self.assertIsNone(row.resale_available_at)
        self.assertIsNotNone(row.created_at.tzinfo)
        self.assertIsNotNone(row.updated_at.tzinfo)

    async def test_times_are_stored_with_time_zone(self):
        item_id = await self.make_item(resale_available_at=NOW)
        row = await self.run_statement(
            select(self.items).where(self.items.c.id == item_id), fetch="one"
        )
        self.assertEqual(row.acquired_at, NOW)
        self.assertEqual(row.resale_available_at, NOW)

    async def test_item_needs_an_existing_definition(self):
        await self.assert_rejected(self.items, item_values(999999))

    async def test_item_status_and_origin_are_checked(self):
        definition_id = await self.make_definition()
        for field, value in (("status", "SOLD"), ("origin", "GIFT")):
            with self.subTest(field=field, value=value):
                await self.assert_rejected(
                    self.items, item_values(definition_id, **{field: value})
                )

    async def test_item_required_columns_cannot_be_null(self):
        definition_id = await self.make_definition()
        for field in ("owner_id", "origin", "acquired_at", "item_definition_id"):
            with self.subTest(field=field):
                await self.assert_rejected(
                    self.items, item_values(definition_id, **{field: None})
                )

    async def test_definition_with_items_cannot_be_deleted(self):
        definition_id = await self.make_definition()
        await self.insert(self.items, item_values(definition_id))
        with self.assertRaises(IntegrityError):
            await self.run_statement(
                delete(self.definitions).where(self.definitions.c.id == definition_id)
            )

    # ----- item_events -----
    async def test_event_type_is_checked(self):
        item_id = await self.make_item()
        await self.assert_rejected(self.events, event_values(item_id, event_type="DELETED"))

    async def test_event_owner_combinations_are_checked(self):
        item_id = await self.make_item()
        valid = [
            ("GRANTED", None, 1),
            ("LISTED", 1, 1),
            ("UNLISTED", 1, 1),
            ("TRANSFERRED", 1, 2),
        ]
        for event_type, from_owner_id, to_owner_id in valid:
            with self.subTest(valid=event_type):
                await self.insert(
                    self.events,
                    event_values(
                        item_id,
                        event_type=event_type,
                        from_owner_id=from_owner_id,
                        to_owner_id=to_owner_id,
                    ),
                )
        invalid = [
            ("GRANTED", 1, 1),
            ("LISTED", None, 1),
            ("LISTED", 1, 2),
            ("UNLISTED", 1, 2),
            ("TRANSFERRED", 1, 1),
            ("TRANSFERRED", None, 2),
            ("GRANTED", None, None),
        ]
        for event_type, from_owner_id, to_owner_id in invalid:
            with self.subTest(invalid=(event_type, from_owner_id, to_owner_id)):
                await self.assert_rejected(
                    self.events,
                    event_values(
                        item_id,
                        event_type=event_type,
                        from_owner_id=from_owner_id,
                        to_owner_id=to_owner_id,
                    ),
                )

    async def test_event_listing_and_trade_ids_do_not_need_other_tables(self):
        item_id = await self.make_item()
        await self.insert(
            self.events, event_values(item_id, listing_id=987654, trade_id=123456)
        )

    async def test_event_needs_an_existing_item(self):
        await self.assert_rejected(self.events, event_values(999999))

    async def test_item_with_events_cannot_be_deleted(self):
        item_id = await self.make_item()
        await self.insert(self.events, event_values(item_id))
        with self.assertRaises(IntegrityError):
            await self.run_statement(delete(self.items).where(self.items.c.id == item_id))

    async def test_event_created_at_is_filled_by_the_database(self):
        item_id = await self.make_item()
        event_id = await self.insert(self.events, event_values(item_id))
        row = await self.run_statement(
            select(self.events).where(self.events.c.id == event_id), fetch="one"
        )
        self.assertIsNotNone(row.created_at.tzinfo)

    async def test_ids_are_generated_by_the_database(self):
        first = await self.make_definition(code="first_code")
        second = await self.make_definition(code="second_code")
        self.assertEqual((first, second), (1, 2))


if __name__ == "__main__":
    unittest.main()

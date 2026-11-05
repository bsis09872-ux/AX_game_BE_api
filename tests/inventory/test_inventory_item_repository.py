"""개별 아이템 저장소(InventoryItemRepository) 테스트: 진짜 PostgreSQL로 읽기·잠금·저장·이력 저장을 확인한다

- 테스트마다 전용 스키마(u05_item_repo_test)를 만들고 그 안에서만 테이블을 만들고 지운다. 개발용 테이블은 건드리지 않는다
- 저장소는 flush까지만 하고 commit하지 않는다. 다른 세션에서 보이는지, rollback하면 이력도 사라지는지로 확인한다
- 행 잠금은 다른 세션에서 NOWAIT로 같은 행을 잠가 보려는 시도가 거절되는지로 확인한다
- 환경 변수 DATABASE_URL(또는 루트 .env)이 없으면 건너뛴다
- database.py와 모델은 import하는 순간 DATABASE_URL을 요구해서 테스트 안에서 import한다
"""

import itertools
import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

SCHEMA = "u05_item_repo_test"
NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
MINUTE = timedelta(minutes=1)
HOUR = timedelta(hours=1)


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


@unittest.skipUnless(
    os.environ.get("DATABASE_URL"), "DATABASE_URL이 없어 저장소 테스트를 건너뛴다"
)
class InventoryItemRepositoryTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import database
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from inventory.domain import enums, exceptions
        from inventory.domain.inventory_item import InventoryItem
        from inventory.domain.item_definition import ItemDefinition
        from inventory.domain.item_event import ItemEvent
        from inventory.infrastructure import models, repositories

        self.numbers = itertools.count(1)
        self.ItemEvent = ItemEvent
        self.enums = enums
        self.exceptions = exceptions
        self.InventoryItem = InventoryItem
        self.ItemDefinition = ItemDefinition
        self.models = models
        self.ItemRepository = repositories.InventoryItemRepository
        self.DefinitionRepository = repositories.ItemDefinitionRepository
        self.items = models.InventoryItemModel.__table__
        self.definitions = models.ItemDefinitionModel.__table__
        self.events = models.ItemEventModel.__table__
        self.engine = database.engine
        # 테스트마다 이벤트 루프가 달라서 남은 연결을 닫고 새로 시작한다
        await self.engine.dispose()
        async with self.engine.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
            await connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
            scoped = await connection.execution_options(
                schema_translate_map={None: SCHEMA}
            )
            await scoped.run_sync(
                lambda sync_connection: database.Base.metadata.create_all(
                    sync_connection, tables=[self.definitions, self.items, self.events]
                )
            )
        self.session_factory = async_sessionmaker(
            self.engine.execution_options(schema_translate_map={None: SCHEMA}),
            expire_on_commit=False,
        )

    async def asyncTearDown(self):
        async with self.engine.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        await self.engine.dispose()

    # ----- 도우미 -----
    async def make_definition(self, **overrides):
        async with self.session_factory() as session:
            definition = await self.DefinitionRepository(session).save(
                self.ItemDefinition(**definition_values(**overrides))
            )
            await session.commit()
        return definition

    async def make_item(self, definition=None, owner_id=1, now=NOW, actor_id=None):
        """새 아이템을 지급해 저장하고 commit한 뒤 id가 붙은 도메인 객체를 돌려준다"""
        # 카탈로그를 안 넘기면 code가 겹치지 않게 번호를 붙여 새로 만든다
        definition = definition or await self.make_definition(
            code=f"item_{next(self.numbers)}"
        )
        item = self.InventoryItem.grant(
            definition, owner_id, self.enums.ItemOrigin.REWARD, now, actor_id=actor_id
        )
        async with self.session_factory() as session:
            await self.ItemRepository(session).save(item)
            await session.commit()
        return item

    async def load(self, item_id):
        async with self.session_factory() as session:
            return await self.ItemRepository(session).find_by_id(item_id)

    async def change(self, item_id, action):
        """아이템을 읽어 도메인 메서드로 바꾸고 저장한 뒤 commit한다"""
        async with self.session_factory() as session:
            repository = self.ItemRepository(session)
            item = await repository.find_by_id(item_id)
            action(item)
            await repository.save(item)
            await session.commit()

    async def events_of(self, item_id):
        async with self.session_factory() as session:
            events, _ = await self.ItemRepository(session).find_events(item_id, size=100)
        return events

    async def raw_item_row(self, item_id):
        async with self.session_factory() as session:
            result = await session.execute(select(self.items).where(self.items.c.id == item_id))
            return result.one()

    # ----- 새 아이템 저장과 읽기 -----
    async def test_save_new_item_gives_it_an_id_and_find_by_id_returns_it_with_its_definition(self):
        definition = await self.make_definition()
        item = await self.make_item(definition, owner_id=7)
        self.assertIsInstance(item.id, int)
        found = await self.load(item.id)
        self.assertIsInstance(found, self.InventoryItem)
        self.assertEqual(found.id, item.id)
        self.assertEqual(found.owner_id, 7)
        self.assertIs(found.status, self.enums.ItemStatus.OWNED)
        self.assertIs(found.origin, self.enums.ItemOrigin.REWARD)
        self.assertEqual(found.acquired_at, NOW)
        self.assertIsNone(found.resale_available_at)
        self.assertIsInstance(found.definition, self.ItemDefinition)
        self.assertEqual((found.definition.id, found.definition.code), (definition.id, "golden_carp"))

    async def test_find_by_id_returns_none_when_missing(self):
        async with self.session_factory() as session:
            self.assertIsNone(await self.ItemRepository(session).find_by_id(999999))

    async def test_saving_a_new_item_also_stores_its_granted_event(self):
        item = await self.make_item(owner_id=7, actor_id=99)
        events = await self.events_of(item.id)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertIs(event.event_type, self.enums.ItemEventType.GRANTED)
        self.assertEqual((event.from_owner_id, event.to_owner_id, event.actor_id), (None, 7, 99))
        self.assertEqual(event.created_at, NOW)

    async def test_save_hands_the_events_over_so_a_second_save_adds_nothing(self):
        item = await self.make_item()
        self.assertEqual(item.pop_events(), [])
        async with self.session_factory() as session:
            await self.ItemRepository(session).save(item)
            await session.commit()
        self.assertEqual(len(await self.events_of(item.id)), 1)

    # ----- 기존 아이템 저장 -----
    async def test_save_updates_the_item_and_appends_events_in_order(self):
        item = await self.make_item()
        await self.change(item.id, lambda i: i.reserve_for_listing(1, NOW + MINUTE, listing_id=77))
        listed = await self.load(item.id)
        self.assertIs(listed.status, self.enums.ItemStatus.LISTED)
        await self.change(
            item.id, lambda i: i.transfer_to(2, NOW + 2 * MINUTE, listing_id=77, trade_id=88)
        )
        traded = await self.load(item.id)
        self.assertEqual(traded.owner_id, 2)
        self.assertIs(traded.status, self.enums.ItemStatus.OWNED)
        self.assertIs(traded.origin, self.enums.ItemOrigin.TRADE)
        self.assertEqual(traded.acquired_at, NOW + 2 * MINUTE)
        self.assertEqual(traded.resale_available_at, NOW + 32 * MINUTE)
        events = await self.events_of(item.id)
        self.assertEqual(
            [event.event_type for event in events],
            [
                self.enums.ItemEventType.GRANTED,
                self.enums.ItemEventType.LISTED,
                self.enums.ItemEventType.TRANSFERRED,
            ],
        )
        self.assertEqual((events[1].listing_id, events[1].actor_id), (77, 1))
        last = events[2]
        self.assertEqual((last.from_owner_id, last.to_owner_id), (1, 2))
        self.assertEqual((last.listing_id, last.trade_id), (77, 88))

    async def test_saving_an_update_touches_only_that_row(self):
        target = await self.make_item(owner_id=1)
        other = await self.make_item(owner_id=2)
        await self.change(target.id, lambda i: i.reserve_for_listing(1, NOW + MINUTE))
        untouched = await self.load(other.id)
        self.assertIs(untouched.status, self.enums.ItemStatus.OWNED)
        self.assertEqual(len(await self.events_of(other.id)), 1)

    async def test_saving_an_update_refreshes_updated_at(self):
        item = await self.make_item()
        before = (await self.raw_item_row(item.id)).updated_at
        await self.change(item.id, lambda i: i.reserve_for_listing(1, NOW + MINUTE))
        after = (await self.raw_item_row(item.id)).updated_at
        self.assertGreater(after, before)

    async def test_saving_an_unknown_id_raises_item_not_found(self):
        definition = await self.make_definition()
        ghost = self.InventoryItem(
            definition,
            1,
            self.enums.ItemStatus.OWNED,
            self.enums.ItemOrigin.REWARD,
            NOW,
            id=999999,
        )
        async with self.session_factory() as session:
            with self.assertRaises(self.exceptions.ItemNotFoundError):
                await self.ItemRepository(session).save(ghost)

    # ----- commit하지 않는다 -----
    async def test_save_flushes_but_does_not_commit(self):
        definition = await self.make_definition()
        item = self.InventoryItem.grant(definition, 1, self.enums.ItemOrigin.REWARD, NOW)
        async with self.session_factory() as writer, self.session_factory() as reader:
            await self.ItemRepository(writer).save(item)
            self.assertIsNotNone(await self.ItemRepository(writer).find_by_id(item.id))
            self.assertIsNone(await self.ItemRepository(reader).find_by_id(item.id))
            await writer.commit()
            self.assertIsNotNone(await self.ItemRepository(reader).find_by_id(item.id))

    async def test_rollback_removes_the_item_and_its_events_together(self):
        definition = await self.make_definition()
        item = self.InventoryItem.grant(definition, 1, self.enums.ItemOrigin.REWARD, NOW)
        async with self.session_factory() as session:
            await self.ItemRepository(session).save(item)
            await session.rollback()
        async with self.session_factory() as session:
            self.assertIsNone(await self.ItemRepository(session).find_by_id(item.id))
            count = await session.execute(select(func.count()).select_from(self.events))
            self.assertEqual(count.scalar_one(), 0)

    async def test_rollback_of_an_update_restores_state_and_removes_the_new_event(self):
        item = await self.make_item()
        async with self.session_factory() as session:
            repository = self.ItemRepository(session)
            loaded = await repository.find_by_id(item.id)
            loaded.reserve_for_listing(1, NOW + MINUTE)
            await repository.save(loaded)
            await session.rollback()
        again = await self.load(item.id)
        self.assertIs(again.status, self.enums.ItemStatus.OWNED)
        self.assertEqual(len(await self.events_of(item.id)), 1)

    # ----- 행 잠금 -----
    async def test_find_by_id_for_update_returns_the_item_or_none(self):
        item = await self.make_item(owner_id=5)
        async with self.session_factory() as session:
            repository = self.ItemRepository(session)
            found = await repository.find_by_id_for_update(item.id)
            missing = await repository.find_by_id_for_update(999999)
        self.assertEqual(
            (found.id, found.owner_id, found.definition.code),
            (item.id, 5, item.definition.code),
        )
        self.assertIsNone(missing)

    async def try_nowait_lock(self, session, table, row_id):
        statement = select(table.c.id).where(table.c.id == row_id).with_for_update(nowait=True)
        await session.execute(statement)

    async def test_find_by_id_for_update_locks_the_item_row_until_the_transaction_ends(self):
        item = await self.make_item()
        async with self.session_factory() as holder, self.session_factory() as other:
            await self.ItemRepository(holder).find_by_id_for_update(item.id)
            with self.assertRaises(DBAPIError):
                await self.try_nowait_lock(other, self.items, item.id)
            await other.rollback()
            await holder.rollback()
            await self.try_nowait_lock(other, self.items, item.id)

    async def test_plain_find_by_id_does_not_lock(self):
        item = await self.make_item()
        async with self.session_factory() as reader, self.session_factory() as other:
            await self.ItemRepository(reader).find_by_id(item.id)
            await self.try_nowait_lock(other, self.items, item.id)

    async def test_find_by_id_for_update_does_not_lock_the_catalog_row(self):
        item = await self.make_item()
        async with self.session_factory() as holder, self.session_factory() as other:
            await self.ItemRepository(holder).find_by_id_for_update(item.id)
            await self.try_nowait_lock(other, self.definitions, item.definition.id)

    async def test_find_by_id_for_update_returns_the_latest_state_even_if_already_read(self):
        item = await self.make_item()
        async with self.session_factory() as session:
            repository = self.ItemRepository(session)
            before = await repository.find_by_id(item.id)
            self.assertIs(before.status, self.enums.ItemStatus.OWNED)
            # 다른 세션이 그 사이에 상태를 바꾸고 commit한다
            await self.change(item.id, lambda i: i.reserve_for_listing(1, NOW + MINUTE))
            latest = await repository.find_by_id_for_update(item.id)
        self.assertIs(latest.status, self.enums.ItemStatus.LISTED)

    # ----- 내 아이템 목록 -----
    async def test_find_by_owner_returns_only_that_owners_items_with_the_total(self):
        definition = await self.make_definition()
        await self.make_item(definition, owner_id=1)
        await self.make_item(definition, owner_id=1)
        await self.make_item(definition, owner_id=2)
        async with self.session_factory() as session:
            repository = self.ItemRepository(session)
            mine, total = await repository.find_by_owner(1)
            nobody, nobody_total = await repository.find_by_owner(99)
        self.assertEqual((len(mine), total), (2, 2))
        self.assertTrue(all(item.owner_id == 1 for item in mine))
        self.assertTrue(all(isinstance(item.definition, self.ItemDefinition) for item in mine))
        self.assertEqual((nobody, nobody_total), ([], 0))

    async def test_find_by_owner_filters_by_status_category_and_rarity(self):
        fish = await self.make_definition(code="fish_rare", name="가", category="FISH", rarity="RARE")
        gem = await self.make_definition(code="gem_epic", name="나", category="GEM", rarity="EPIC")
        fish_item = await self.make_item(fish)
        await self.make_item(gem)
        await self.change(fish_item.id, lambda i: i.reserve_for_listing(1, NOW + MINUTE))
        async with self.session_factory() as session:
            repository = self.ItemRepository(session)
            everything, everything_total = await repository.find_by_owner(1)
            listed, listed_total = await repository.find_by_owner(1, status="LISTED")
            owned, owned_total = await repository.find_by_owner(1, status="OWNED")
            gems, gems_total = await repository.find_by_owner(1, category="GEM")
            rare, rare_total = await repository.find_by_owner(1, rarity="RARE")
            none, none_total = await repository.find_by_owner(1, category="MISC")
        self.assertEqual(everything_total, 2)
        self.assertEqual(([i.id for i in listed], listed_total), ([fish_item.id], 1))
        self.assertEqual((owned_total, owned[0].definition.code), (1, "gem_epic"))
        self.assertEqual((gems[0].definition.code, gems_total), ("gem_epic", 1))
        self.assertEqual((rare[0].definition.code, rare_total), ("fish_rare", 1))
        self.assertEqual((none, none_total), ([], 0))

    async def test_find_by_owner_defaults_to_the_most_recently_acquired_first(self):
        definition = await self.make_definition()
        oldest = await self.make_item(definition, now=NOW)
        newest = await self.make_item(definition, now=NOW + 2 * HOUR)
        middle = await self.make_item(definition, now=NOW + HOUR)
        async with self.session_factory() as session:
            found, _ = await self.ItemRepository(session).find_by_owner(1)
        self.assertEqual([i.id for i in found], [newest.id, middle.id, oldest.id])

    async def test_find_by_owner_sorts_rarity_by_rank_not_alphabet(self):
        for rarity in ("COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY"):
            definition = await self.make_definition(
                code=f"item_{rarity.lower()}", name=rarity, rarity=rarity
            )
            await self.make_item(definition)
        async with self.session_factory() as session:
            found, _ = await self.ItemRepository(session).find_by_owner(1, sort="rarity_desc")
        self.assertEqual(
            [i.definition.name for i in found],
            ["LEGENDARY", "EPIC", "RARE", "UNCOMMON", "COMMON"],
        )

    async def test_find_by_owner_sorts_by_definition_name(self):
        for code, name in (("item_3", "다"), ("item_1", "가"), ("item_2", "나")):
            await self.make_item(await self.make_definition(code=code, name=name))
        async with self.session_factory() as session:
            found, _ = await self.ItemRepository(session).find_by_owner(1, sort="name_asc")
        self.assertEqual([i.definition.name for i in found], ["가", "나", "다"])

    async def test_find_by_owner_returns_the_page_and_the_total(self):
        definition = await self.make_definition()
        made = [await self.make_item(definition, now=NOW + n * MINUTE) for n in range(5)]
        newest_first = [item.id for item in reversed(made)]
        async with self.session_factory() as session:
            repository = self.ItemRepository(session)
            first, total = await repository.find_by_owner(1, page=1, size=2)
            last, last_total = await repository.find_by_owner(1, page=3, size=2)
            beyond, beyond_total = await repository.find_by_owner(1, page=4, size=2)
        self.assertEqual(([i.id for i in first], total), (newest_first[:2], 5))
        self.assertEqual(([i.id for i in last], last_total), (newest_first[4:], 5))
        self.assertEqual((beyond, beyond_total), ([], 5))

    # ----- 이력 조회 -----
    async def test_find_events_returns_oldest_first_with_page_and_total(self):
        item = await self.make_item()
        await self.change(item.id, lambda i: i.reserve_for_listing(1, NOW + MINUTE))
        await self.change(item.id, lambda i: i.release_from_listing(1, NOW + 2 * MINUTE))
        async with self.session_factory() as session:
            repository = self.ItemRepository(session)
            first, total = await repository.find_events(item.id, page=1, size=2)
            last, last_total = await repository.find_events(item.id, page=2, size=2)
        types = self.enums.ItemEventType
        self.assertEqual(([e.event_type for e in first], total), ([types.GRANTED, types.LISTED], 3))
        self.assertEqual(([e.event_type for e in last], last_total), ([types.UNLISTED], 3))
        self.assertTrue(all(isinstance(event, self.ItemEvent) for event in first))

    async def test_find_events_returns_only_that_items_events(self):
        first_item = await self.make_item(owner_id=1)
        await self.make_item(owner_id=2)
        async with self.session_factory() as session:
            events, total = await self.ItemRepository(session).find_events(first_item.id)
            none, none_total = await self.ItemRepository(session).find_events(999999)
        self.assertEqual((len(events), total), (1, 1))
        self.assertEqual((none, none_total), ([], 0))

    # ----- 판매 예약 중인 아이템이 있는지 -----
    async def test_has_listed_items_is_true_only_while_that_owner_has_a_listed_item(self):
        definition = await self.make_definition()
        item = await self.make_item(definition, owner_id=1)
        await self.make_item(definition, owner_id=2)
        async with self.session_factory() as session:
            self.assertFalse(await self.ItemRepository(session).has_listed_items(1))
        await self.change(item.id, lambda i: i.reserve_for_listing(1, NOW + MINUTE))
        async with self.session_factory() as session:
            repository = self.ItemRepository(session)
            self.assertTrue(await repository.has_listed_items(1))
            self.assertFalse(await repository.has_listed_items(2))
            self.assertFalse(await repository.has_listed_items(99))
        await self.change(item.id, lambda i: i.release_from_listing(1, NOW + 2 * MINUTE))
        async with self.session_factory() as session:
            self.assertFalse(await self.ItemRepository(session).has_listed_items(1))


if __name__ == "__main__":
    unittest.main()

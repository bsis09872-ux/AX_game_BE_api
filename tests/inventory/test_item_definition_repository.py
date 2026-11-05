"""아이템 카탈로그 저장소(ItemDefinitionRepository) 테스트: 진짜 PostgreSQL로 읽기·저장·조회·삭제를 확인한다

- 테스트마다 전용 스키마(u05_repo_test)를 만들고 그 안에서만 테이블을 만들고 지운다. 개발용 테이블은 건드리지 않는다
- 저장소는 flush까지만 하고 commit하지 않는다. 다른 세션에서 보이는지로 확인한다
- 환경 변수 DATABASE_URL(또는 루트 .env)이 없으면 건너뛴다
- database.py와 모델은 import하는 순간 DATABASE_URL을 요구해서 테스트 안에서 import한다
"""

import os
import unittest
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

SCHEMA = "u05_repo_test"
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


@unittest.skipUnless(
    os.environ.get("DATABASE_URL"), "DATABASE_URL이 없어 저장소 테스트를 건너뛴다"
)
class ItemDefinitionRepositoryTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import database
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from inventory.domain.exceptions import DefinitionNotFoundError
        from inventory.domain.item_definition import ItemDefinition
        from inventory.infrastructure import models
        from inventory.infrastructure.repositories import ItemDefinitionRepository

        self.ItemDefinition = ItemDefinition
        self.ItemDefinitionRepository = ItemDefinitionRepository
        self.DefinitionNotFoundError = DefinitionNotFoundError
        self.models = models
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
                    sync_connection,
                    tables=[
                        models.ItemDefinitionModel.__table__,
                        models.InventoryItemModel.__table__,
                        models.ItemEventModel.__table__,
                    ],
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
    def new_definition(self, **overrides):
        return self.ItemDefinition(**definition_values(**overrides))

    async def save_committed(self, **overrides):
        """새 카탈로그를 저장하고 commit한 뒤 id가 붙은 도메인 객체를 돌려준다"""
        async with self.session_factory() as session:
            definition = await self.ItemDefinitionRepository(session).save(
                self.new_definition(**overrides)
            )
            await session.commit()
        return definition

    async def add_item(self, definition_id):
        async with self.session_factory() as session:
            session.add(
                self.models.InventoryItemModel(
                    item_definition_id=definition_id,
                    owner_id=1,
                    origin="REWARD",
                    acquired_at=NOW,
                )
            )
            await session.commit()

    # ----- 저장(새로 만들기)과 읽기 -----
    async def test_save_new_definition_gives_it_an_id_and_find_by_id_returns_all_fields(self):
        saved = await self.save_committed(
            description="반짝인다", icon="fish_golden", weight=3, fishable=False
        )
        self.assertIsInstance(saved.id, int)
        self.assertGreaterEqual(saved.id, 1)
        async with self.session_factory() as session:
            found = await self.ItemDefinitionRepository(session).find_by_id(saved.id)
        self.assertIsInstance(found, self.ItemDefinition)
        self.assertEqual(found.id, saved.id)
        self.assertEqual(
            (found.code, found.name, found.start_price, found.description),
            ("golden_carp", "황금 잉어", 500, "반짝인다"),
        )
        self.assertEqual((found.icon, found.weight, found.fishable), ("fish_golden", 3, False))

    async def test_loaded_category_and_rarity_are_enum_members(self):
        from inventory.domain.enums import ItemCategory, ItemRarity

        saved = await self.save_committed(category="GEM", rarity="EPIC")
        async with self.session_factory() as session:
            found = await self.ItemDefinitionRepository(session).find_by_id(saved.id)
        self.assertIs(found.category, ItemCategory.GEM)
        self.assertIs(found.rarity, ItemRarity.EPIC)

    async def test_find_by_id_returns_none_when_missing(self):
        async with self.session_factory() as session:
            self.assertIsNone(await self.ItemDefinitionRepository(session).find_by_id(999999))

    async def test_find_by_code_finds_the_definition_or_returns_none(self):
        saved = await self.save_committed()
        async with self.session_factory() as session:
            repository = self.ItemDefinitionRepository(session)
            found = await repository.find_by_code("golden_carp")
            missing = await repository.find_by_code("no_such_code")
        self.assertEqual(found.id, saved.id)
        self.assertIsNone(missing)

    # ----- commit하지 않는다 -----
    async def test_save_flushes_but_does_not_commit(self):
        async with self.session_factory() as writer, self.session_factory() as reader:
            definition = await self.ItemDefinitionRepository(writer).save(
                self.new_definition()
            )
            # 같은 세션에서는 보이고, 다른 세션에서는 commit 전까지 안 보인다
            self.assertIsNotNone(
                await self.ItemDefinitionRepository(writer).find_by_id(definition.id)
            )
            self.assertIsNone(
                await self.ItemDefinitionRepository(reader).find_by_code("golden_carp")
            )
            await writer.commit()
            self.assertIsNotNone(
                await self.ItemDefinitionRepository(reader).find_by_code("golden_carp")
            )

    async def test_rollback_removes_a_saved_definition(self):
        async with self.session_factory() as session:
            await self.ItemDefinitionRepository(session).save(self.new_definition())
            await session.rollback()
        async with self.session_factory() as session:
            self.assertIsNone(
                await self.ItemDefinitionRepository(session).find_by_code("golden_carp")
            )

    async def test_saving_a_duplicate_code_is_rejected_by_the_database(self):
        await self.save_committed()
        async with self.session_factory() as session:
            with self.assertRaises(IntegrityError):
                await self.ItemDefinitionRepository(session).save(
                    self.new_definition(name="다른 이름")
                )

    # ----- 저장(고치기) -----
    async def test_save_updates_the_changeable_fields_of_that_row_only(self):
        target = await self.save_committed()
        other = await self.save_committed(code="silver_carp", name="은빛 잉어")
        target.update(
            start_price=999, weight=0, icon="new_icon", fishable=False, description="새 설명"
        )
        async with self.session_factory() as session:
            await self.ItemDefinitionRepository(session).save(target)
            await session.commit()
        async with self.session_factory() as session:
            repository = self.ItemDefinitionRepository(session)
            changed = await repository.find_by_id(target.id)
            untouched = await repository.find_by_id(other.id)
        self.assertEqual(
            (changed.start_price, changed.weight, changed.icon, changed.fishable, changed.description),
            (999, 0, "new_icon", False, "새 설명"),
        )
        self.assertEqual((changed.code, changed.name), ("golden_carp", "황금 잉어"))
        self.assertEqual(
            (untouched.start_price, untouched.weight, untouched.icon, untouched.fishable),
            (500, 10, "default", True),
        )

    async def test_saving_an_update_does_not_create_a_second_row(self):
        saved = await self.save_committed()
        saved.update(start_price=700)
        async with self.session_factory() as session:
            await self.ItemDefinitionRepository(session).save(saved)
            await session.commit()
            _, total = await self.ItemDefinitionRepository(session).find_all()
        self.assertEqual(total, 1)

    async def test_saving_an_unknown_id_raises_definition_not_found(self):
        ghost = self.ItemDefinition(**definition_values(), id=999999)
        async with self.session_factory() as session:
            with self.assertRaises(self.DefinitionNotFoundError):
                await self.ItemDefinitionRepository(session).save(ghost)

    # ----- 목록 -----
    async def make_many(self, count):
        for number in range(1, count + 1):
            await self.save_committed(code=f"item_{number}", name=f"이름{number}")

    async def test_find_all_returns_the_page_and_the_total(self):
        await self.make_many(5)
        async with self.session_factory() as session:
            repository = self.ItemDefinitionRepository(session)
            first, total = await repository.find_all(sort="name_asc", page=1, size=2)
            last, last_total = await repository.find_all(sort="name_asc", page=3, size=2)
            beyond, beyond_total = await repository.find_all(sort="name_asc", page=4, size=2)
        self.assertEqual([d.name for d in first], ["이름1", "이름2"])
        self.assertEqual(total, 5)
        self.assertEqual([d.name for d in last], ["이름5"])
        self.assertEqual(last_total, 5)
        self.assertEqual((beyond, beyond_total), ([], 5))

    async def test_find_all_defaults_to_the_first_page_of_20(self):
        await self.make_many(21)
        async with self.session_factory() as session:
            found, total = await self.ItemDefinitionRepository(session).find_all()
        self.assertEqual((len(found), total), (20, 21))

    async def test_find_all_filters_by_category_and_rarity_and_counts_the_filtered_total(self):
        await self.save_committed(code="fish_rare", name="가", category="FISH", rarity="RARE")
        await self.save_committed(code="fish_epic", name="나", category="FISH", rarity="EPIC")
        await self.save_committed(code="gem_rare", name="다", category="GEM", rarity="RARE")
        async with self.session_factory() as session:
            repository = self.ItemDefinitionRepository(session)
            by_category, category_total = await repository.find_all(category="FISH")
            by_rarity, rarity_total = await repository.find_all(rarity="RARE")
            both, both_total = await repository.find_all(category="GEM", rarity="RARE")
            none, none_total = await repository.find_all(category="MISC")
        self.assertEqual(({d.code for d in by_category}, category_total), ({"fish_rare", "fish_epic"}, 2))
        self.assertEqual(({d.code for d in by_rarity}, rarity_total), ({"fish_rare", "gem_rare"}, 2))
        self.assertEqual(([d.code for d in both], both_total), (["gem_rare"], 1))
        self.assertEqual((none, none_total), ([], 0))

    async def test_find_all_sorts_rarity_by_rank_not_alphabet(self):
        for rarity in ("COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY"):
            await self.save_committed(code=f"item_{rarity.lower()}", name=rarity, rarity=rarity)
        async with self.session_factory() as session:
            found, _ = await self.ItemDefinitionRepository(session).find_all(sort="rarity_desc")
        self.assertEqual(
            [d.name for d in found], ["LEGENDARY", "EPIC", "RARE", "UNCOMMON", "COMMON"]
        )

    async def test_rarity_desc_is_the_default_and_ties_are_ordered_by_name(self):
        await self.save_committed(code="item_b", name="나", rarity="RARE")
        await self.save_committed(code="item_a", name="가", rarity="RARE")
        await self.save_committed(code="item_c", name="다", rarity="EPIC")
        async with self.session_factory() as session:
            found, _ = await self.ItemDefinitionRepository(session).find_all()
        self.assertEqual([d.name for d in found], ["다", "가", "나"])

    async def test_find_all_sorts_by_name(self):
        for code, name in (("item_3", "다"), ("item_1", "가"), ("item_2", "나")):
            await self.save_committed(code=code, name=name)
        async with self.session_factory() as session:
            found, _ = await self.ItemDefinitionRepository(session).find_all(sort="name_asc")
        self.assertEqual([d.name for d in found], ["가", "나", "다"])

    # ----- 아이템 수와 삭제 -----
    async def test_count_items_counts_only_the_items_of_that_definition(self):
        first = await self.save_committed()
        second = await self.save_committed(code="silver_carp", name="은빛 잉어")
        await self.add_item(first.id)
        await self.add_item(first.id)
        await self.add_item(second.id)
        async with self.session_factory() as session:
            repository = self.ItemDefinitionRepository(session)
            counts = (
                await repository.count_items(first.id),
                await repository.count_items(second.id),
                await repository.count_items(999999),
            )
        self.assertEqual(counts, (2, 1, 0))

    async def test_delete_removes_only_that_definition(self):
        target = await self.save_committed()
        other = await self.save_committed(code="silver_carp", name="은빛 잉어")
        async with self.session_factory() as session:
            repository = self.ItemDefinitionRepository(session)
            await repository.delete(target)
            await session.commit()
        async with self.session_factory() as session:
            repository = self.ItemDefinitionRepository(session)
            self.assertIsNone(await repository.find_by_id(target.id))
            self.assertIsNotNone(await repository.find_by_id(other.id))

    async def test_delete_does_not_commit(self):
        target = await self.save_committed()
        async with self.session_factory() as session:
            await self.ItemDefinitionRepository(session).delete(target)
            await session.rollback()
        async with self.session_factory() as session:
            self.assertIsNotNone(await self.ItemDefinitionRepository(session).find_by_id(target.id))

    async def test_delete_is_rejected_by_the_database_while_items_exist(self):
        target = await self.save_committed()
        await self.add_item(target.id)
        async with self.session_factory() as session:
            with self.assertRaises(IntegrityError):
                await self.ItemDefinitionRepository(session).delete(target)

    async def test_delete_of_a_missing_definition_raises_definition_not_found(self):
        ghost = self.ItemDefinition(**definition_values(), id=999999)
        unsaved = self.new_definition()
        async with self.session_factory() as session:
            repository = self.ItemDefinitionRepository(session)
            for definition in (ghost, unsaved):
                with self.subTest(id=definition.id):
                    with self.assertRaises(self.DefinitionNotFoundError):
                        await repository.delete(definition)


if __name__ == "__main__":
    unittest.main()

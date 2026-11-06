"""시드: 카탈로그 13개와 시연용 아이템 24개(이력 24건)를 넣는다

- DB에 직접 INSERT하지 않고 ItemDefinition, InventoryItem.grant를 거쳐 규칙을 통과시킨다. 이력은 grant가 만들고 save가 저장한다
- 여러 번 실행해도 안전하다. 카탈로그는 code로 있으면 건너뛰고, 시연 아이템은 소유자가 아이템을 하나도 안 가졌을 때만 넣는다
- 시연 소유자는 임시 사용자 1, 2, 3이다 (DEMO_ITEMS에서 바꾼다). 활성 사용자인지는 UserLookup 계약으로 묻고, 아니면 그 소유자는 건너뛰고 경고만 남긴다
- run_seed는 flush까지만 하고 commit하지 않는다. commit은 스크립트(main)가 한다
- 테스트할 때는 python -m inventory.infrastructure.seed 로 실행한다 (저장소 루트에서 PYTHONPATH=src, 앱을 한 번 켜서 테이블이 만들어진 뒤에)
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from inventory.application.contracts import UserLookup
from inventory.domain.enums import ItemOrigin
from inventory.domain.inventory_item import InventoryItem
from inventory.domain.item_definition import ItemDefinition
from inventory.infrastructure.repositories import (
    InventoryItemRepository,
    ItemDefinitionRepository
)

logger = logging.getLogger(__name__)

# 아이템 카탈로그
CATALOG = [
    ('crucian_carp', '붕어', 'FISH', 'COMMON', 100, 40, 'fish_carp'),
    ('mackerel', '고등어', 'FISH', 'COMMON', 120, 35, 'fish_mackerel'),
    ('sea_bass', '농어', 'FISH', 'UNCOMMON', 400, 20, 'fish_bass'),
    ('salmon', '연어', 'FISH', 'UNCOMMON', 500, 15, 'fish_salmon'),
    ('pufferfish', '복어', 'FISH', 'RARE', 1500, 8, 'fish_puffer'),
    ('golden_carp', '황금 잉어', 'FISH', 'EPIC', 5000, 3, 'fish_golden'),
    ('sea_dragon', '바다용', 'FISH', 'LEGENDARY', 20000, 1, 'fish_dragon'),
    ('pearl', '진주', 'GEM', 'UNCOMMON', 600, 6, 'gem_pearl'),
    ('sapphire', '사파이어', 'GEM', 'RARE', 2000, 3, 'gem_sapphire'),
    ('black_pearl', '흑진주', 'GEM', 'EPIC', 6000, 1, 'gem_black_pearl'),
    ('old_boot', '낡은 장화', 'MISC', 'COMMON', 30, 12, 'misc_boot'),
    ('seaweed', '해초', 'MISC', 'COMMON', 40, 10, 'misc_seaweed'),
    ('message_bottle', '편지병', 'MISC', 'RARE', 1200, 2, 'misc_bottle'),
]

# 개별 아이템
# 소유자 정보(1, 2, 3)는 임시로 넣어 둔 값
DEMO_ITEMS = {
    'user1': {'crucian_carp': 3, 'mackerel': 2, 'sea_bass': 1, 'pufferfish': 1, 'pearl': 1, 'old_boot': 1},
    'user2': {'crucian_carp': 2, 'salmon': 2, 'sapphire': 1, 'seaweed': 1, 'message_bottle': 1},
    'user3': {
        'mackerel': 1, 'sea_bass': 1, 'golden_carp': 1, 'black_pearl': 1,
        'sea_dragon': 1, 'seaweed': 1, 'crucian_carp': 1, 'old_boot': 1,
    },
}

# 시드 주입
async def run_seed(session: AsyncSession, now: datetime, user_lookup: UserLookup) -> dict[str, int]:
    definition_repository = ItemDefinitionRepository(session)
    item_repository = InventoryItemRepository(session)

    # 1. 카탈로그 13개: code로 찾아서 없을 때만 만든다 (멱등)
    definitions = {}
    created_definitions = 0
    for code, name, category, rarity, start_price, weight, icon in CATALOG:
        definition = await definition_repository.save(
            ItemDefinition(
                code=code,
                name=name,
                category=category,
                rarity=rarity,
                start_price=start_price,
                weight=weight,
                icon=icon
            )
        )
        created_definitions += 1
    definitions[code] = definition

    # 2. 소유자 중 활성 사용자만 계약으로 한 번에 조회한다
    #   → owner_id는 users.id FK이기 때문에 없는 번호로 아이템을 만들면 DB가 거절한다
    active_users = await user_lookup.find_active_user_ids(DEMO_ITEMS)

    # 3. 지정 소유자에게 아이템을 주입한다
    created_items = 0
    for owner_id, wanted in DEMO_ITEMS.items():

        # 활성 사용자가 아니면 건너 뛴다 (카탈로그만 들어감)
        if owner_id not in active_users:
            logger.warning('seed_skipped owner_id=%s reason=user_not_found', owner_id)
            continue

        # 이미 아이템이 하나라도 있는 소유자는 건너뛴다 (멱등)
        # 중복 소유를 막는다는 의미가 아니라 시드 주입을 여러 번 할 때 계속 들어가는 걸 막기 위함
        _, total = await item_repository.find_by_owner(owner_id, size=1)
        if total:
            continue

        for code, count in wanted.items():
            for _ in range(count):
                # GRANTED 이력 생성 (출처: SEED, 요청자: 관리자(Null))
                item = InventoryItem.grant(definitions[code], owner_id, ItemOrigin.SEED, now)
                # save가 아이템과 쌓인 이력을 같이 저장(flush) 한다
                await item_repository.save(item)
                created_items += 1

    return {'definitions': created_definitions, 'items': created_items}

# 일회성 실행 스크립트
# 테이블을 생성하는 게 아니라 시드를 넣고 커밋하는 용도
async def main() -> None:
    # 테스트 할 때 환경변수 없이도 돌도록 함수 안에서 모듈 임포트
    from database import AsyncSessionLocal, engine
    from inventory.wiring import build_user_lookup
    from shared.core.logging_config import setup_logging

    setup_logging()

    # 커밋
    async with AsyncSessionLocal() as session:
        result = await run_seed(session, datetime.now(timezone.utc), build_user_lookup(session))
        await session.commit()

    print(result)
    await engine.dispose() # 깔끔하게 종료!

if __name__ == '__main__':
    asyncio.run(main())
"""시드: 카탈로그 13개와 시연용 아이템 24개(이력 24건)를 넣는다

- DB에 직접 INSERT하지 않고 ItemDefinition, InventoryItem.grant를 거쳐 규칙을 통과시킨다. 이력은 grant가 만들고 save가 저장한다
- 여러 번 실행해도 안전하다. 카탈로그는 code로 있으면 건너뛰고, 시연 아이템은 소유자가 아이템을 하나도 안 가졌을 때만 넣는다
- 시연 소유자는 임시 사용자 1, 2, 3이다 (DEMO_ITEMS에서 바꾼다). 사용자가 없으면 그 소유자는 건너뛰고 경고만 남긴다
- run_seed는 flush까지만 하고 commit하지 않는다. commit은 스크립트(main)가 한다
- python -m inventory.infrastructure.seed 로 실행한다 (저장소 루트에서 PYTHONPATH=src)
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    1: {'crucian_carp': 3, 'mackerel': 2, 'sea_bass': 1, 'pufferfish': 1, 'pearl': 1, 'old_boot': 1},
    2: {'crucian_carp': 2, 'salmon': 2, 'sapphire': 1, 'seaweed': 1, 'message_bottle': 1},
    3: {
        'mackerel': 1, 'sea_bass': 1, 'golden_carp': 1, 'black_pearl': 1,
        'sea_dragon': 1, 'seaweed': 1, 'crucian_carp': 1, 'old_boot': 1,
    },
}

# 시드 주입

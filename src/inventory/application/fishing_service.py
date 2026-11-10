"""낚시 서비스: 한 번 낚는 흐름을 맡는다 (쿨다운 확인 -> 후보 조회/추첨 -> 아이템 지급)

- 쿨다운을 먼저 확인한다. 쿨다운 중이면 후보 조회도 추첨도 지급도 하지 않는다
- 지급은 InventoryService.grant_item에 맡긴다 (저장, commit, 성공 로그, 활성 사용자 확인). 여기서 따로 commit하거나 로그를 남기지 않는다
- 지급 출처는 REWARD이고 요청자(actor)는 비운다 (시스템 지급)
- 월드 투척에서 소비한 쿨다운은 결과 요청 실패로 되돌리지 않는다
- 월드 서비스가 위치/입질을 확인한 뒤 prepare_verified_reward를 호출한다
- 난수 발생기는 밖에서 받는다 (테스트에서 결과를 정해 놓을 수 있게 한다)
- FastAPI와 SQLAlchemy의 세부 사항을 모른다
"""

from datetime import datetime

from inventory.application.contracts import DefinitionRepository, FishingCooldown
from inventory.application.dto import ItemInfo
from inventory.application.service import InventoryService

from inventory.domain.enums import ItemOrigin
from inventory.domain.exceptions import FishingCooldownError
from inventory.domain.fishing import pick_fishing_reward

class FishingService:

    def __init__(
        self,
        definitions: DefinitionRepository,
        cooldown: FishingCooldown,
        inventory: InventoryService,
        rng
    ) -> None:
        self._definitions = definitions
        self._cooldown = cooldown
        self._inventory = inventory
        self._rng = rng


    # 한 번 낚기
    async def go_fishing(self, user_id: int, now: datetime) -> ItemInfo:
        # 공유 쿨다운을 확인한 뒤 기존 추첨과 지급 규칙을 사용한다.
        remaining = await self._cooldown.try_start(user_id, now)
        if remaining > 0:
            raise FishingCooldownError(remaining)

        candidates = await self._definitions.find_fishable()
        definition = pick_fishing_reward(candidates, self._rng)
        return await self._inventory.grant_item(definition.id, user_id, ItemOrigin.REWARD, now)


    async def prepare_verified_reward(self, user_id: int, now: datetime) -> ItemInfo:
        """투척 쿨다운과 입질을 검증한 월드 서비스가 기존 지급 규칙을 재사용한다."""
        candidates = await self._definitions.find_fishable()
        definition = pick_fishing_reward(candidates, self._rng)
        return await self._inventory.grant_item_in_transaction(definition.id, user_id, ItemOrigin.REWARD, now)


    async def start_cooldown(self, user_id: int, now: datetime) -> int:
        return await self._cooldown.try_start(user_id, now)

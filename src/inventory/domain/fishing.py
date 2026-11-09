"""낚시 추첨: 가중치에 비례해 지급할 카탈로그를 하나 뽑는다

- 후보는 fishable=True이고 weight가 0보다 큰 카탈로그뿐이다
- 후보가 없거나 weight 합이 0이면 NoFishableDefinitionError다 (지급하지 않는다)
- 0 이상 weight 합 미만의 정수 하나를 뽑아서 앞에서부터 weight를 더해 가며 그 수가 속한 구간의 카탈로그를 고른다
- 난수 발생기는 인자로 받는다 (테스트에서 결과를 정해 놓을 수 있게 한다)
- 순수 파이썬만 쓴다 (FastAPI, Pydantic, SQLAlchemy, logging을 import하지 않는다)
"""

from collections.abc import Iterable

from inventory.domain.exceptions import NoFishableDefinitionError
from inventory.domain.item_definition import ItemDefinition

def pick_fishing_reward(definitions: Iterable[ItemDefinition], rng) -> ItemDefinition:

    # 1. 후보만 거른다 (입력은 바꾸지 않는다)
    candidates = [d for d in definitions if d.fishable and d.weight > 0]
    total = sum(d.weight for d in candidates)
    if total == 0:
        raise NoFishableDefinitionError()

    # 2. 뽑기 로직 상세
    # 2-1. 0 이상 total 미만의 수 하나를 짚는다
    roll = rng.randrange(total)
    upto = 0

    for definition in candidates:
        upto += definition.weight # 2-2. 첫 번째 가중치 범위
        if roll < upto:           # 2-3. 짚은 수가 N번째 가중치 합 이내면
            return definition     # 2-4. N번째 카탈로그를 반환 
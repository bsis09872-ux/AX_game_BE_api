"""레포지토리: 도메인 객체를 DB에 저장하고 읽는다

- commit하지 않는다. flush까지만 하고 commit은 서비스가 하며, 오류 때 rollback은 팀 공통 get_db가 한다
- find_by_id_for_update는 SELECT ... FOR UPDATE로 행을 잠그고, 잠근 뒤의 최신 상태를 돌려준다
- save(item)은 아이템과 쌓인 이력(pop_events)을 같은 트랜잭션에 저장한다
- 이력은 추가와 조회만 있다 (수정이나 삭제하는 메서드를 만들지 않는다)
- 읽기 메서드는 DB 상태를 바꾸지 않는다
- 업무 규칙을 판정하지 않는다 (규칙은 도메인에 있다)
- ItemDefinitionRepository는 아이템 카탈로그를 저장하고 읽는다. 같은 code와 아이템이 있는 카탈로그 삭제는 DB가 거절하고 저장소는 그 오류를 그대로 올려 보낸다 (서비스가 변환한다)
- 목록은 (도메인 객체 목록, 총개수)를 돌려준다. 희귀도는 순위(COMMON이 가장 낮음)로 정렬하고 동점은 name, id 순이다
- ORM 모델은 이 파일 밖으로 내보내지 않는다 (도메인 객체로 바꿔 돌려준다)
"""

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.domain.enums import ItemRarity
from inventory.domain.exceptions import DefinitionNotFoundError
from inventory.domain.item_definition import ItemDefinition
# 테이블 모델은 이 파일 안에서만 쓰고 밖으로는 ItemDefinition(도메인 객체)만 내보낸다
from inventory.infrastructure.models import InventoryItemModel, ItemDefinitionModel

# 희귀도를 글자 순서가 아니라 순위로 정렬
# {'COMMON': 1, 'UNCOMMON': 2, 'RARE': 3, 'EPIC': 4, 'LEGENDARY': 5}가 생성됨
_RARITY_RANK = case(
    {rarity.value: rank for rank, rarity in enumerate(ItemRarity, start=1)},
    value=ItemDefinitionModel.rarity
)

# 페이지마다 정렬이 엉키지 않도록 함
_SORTS = {
    'rarity_desc': (_RARITY_RANK.desc(), ItemDefinitionModel.name, ItemDefinitionModel.id),
    'name_asc': (ItemDefinitionModel.name, ItemDefinitionModel.id)
}

def _to_domain(row: ItemDefinitionModel) -> ItemDefinition:
    # 레코드 하나가 도메인 객체가 된다
    return ItemDefinition(
        code=row.code,
        name=row.name,
        category=row.category,
        rarity=row.rarity,
        start_price=row.start_price,
        description=row.description,
        icon=row.icon,
        weight=row.weight,
        fishable=row.fishable,
        id=row.id
    )

    # await 규칙
    # - await를 붙이는 것: DB까지 다녀오는 일 (session.get, session.execute, session.flush)
    #   DB 응답을 기다리는 동안 다른 일을 할 수 있게 async로 만든 함수라서 await를 붙여야 실제로 실행된다
    #   await를 빼면 실행되지 않고 "coroutine was never awaited" 경고만 나오며,
    #   돌려받은 값도 결과가 아니라 코루틴 객체라서 그 뒤의 .scalar_one() 같은 호출이 오류가 난다
    # - await를 안 붙이는 것: 메모리 안에서 끝나는 일
    #   session.add(row): 세션에 "저장할 것"으로 올려 두기만 한다. DB에는 flush 때 나간다
    #   result.scalar_one() 등: execute가 이미 가져온 결과를 꺼내 볼 뿐이다
    #   select(...), 모델 객체 만들기: SQL 문장이나 객체를 만들 뿐 DB를 부르지 않는다

class ItemDefinitionRepository:

    # 세션은 레포지토리가 직접 만들지 않고 서비스가 만들어 넘겨준다
    # 같은 세션으로 다른 저장소를 쓰면 하나의 트랜잭션으로 묶인다
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # 기본키(id)로 레코드를 찾는다
    async def find_by_id(self, definition_id: int) -> ItemDefinition | None:
        row = await self._session.get(ItemDefinitionModel, definition_id)
        return None if row is None else _to_domain(row)

    # 코드(code)로 레코드를 찾는다 (기본키가 아니기 때문에 session.get 대신 select 사용)
    async def find_by_code(self, code: str) -> ItemDefinition | None:
        result = await self._session.execute(
            select(ItemDefinitionModel).where(ItemDefinitionModel.code == code)
        )
        row = result.scalar_one_or_none() # code는 unique이기 때문에 one_or_none
        return None if row is None else _to_domain(row)

    # (해당 페이지의) 목록을 받는다 + 덤으로 받는 목록의 length 까지 (= total)
    async def find_all(
            # 별표 역할: 별표 뒤의 인자는 이름을 붙여서만 넘길 수 있다 (값이 엉뚱하게 들어가지 않도록)
            self, *, category=None, rarity=None, sort='rarity_desc', page=1, size=20
    ) -> tuple[list[ItemDefinition], int]:

        # 조건 초기화, 조건이 있으면 조건부 조회 + 조건이 없으면 전체 조회 
        conditions = []
        if category is not None:
            conditions.append(ItemDefinitionModel.category == category)
        if rarity is not None:
            conditions.append(ItemDefinitionModel.rarity == rarity)

        # 받는 목록의 length (프론트가 총 몇 페이지가 나올지 판단할 때 사용)
        total = (
            await self._session.execute(
                select(func.count()).select_from(ItemDefinitionModel).where(*conditions)
            )
        ).scalar_one()  # scalar_one(): 1행 1열의 값을 꺼낸다. total은 항상 1행이라서 맞다
        
        rows = (
            await self._session.execute(
                select(ItemDefinitionModel)
                .where(*conditions)
                # 모르는 sort 값이 오면 오류 발생 → 정렬 강제 성격 재확인
                .order_by(*_SORTS[sort])
                .limit(size) # 한 페이지에서 몇 개를 받을 건지
                .offset((page-1) * size) # 앞 페이지에서 받은 만큼 건너뛴다
            )
        ).scalars() 
        # 여러 행에서 각 행의 첫 번째 열만 꺼내 순회할 수 있게 한다 / 행이 0개면 빈 목록 (오류 아님)
        # .scalar로 쓰려면 인덱싱해야 조회할 수 있다
        # 그리고 .scalar는 행이 2개 이상이어도 첫 행을 돌려주므로 실수를 숨긴다 
        #   → 한 행을 뽑고 싶을 때는 혹시 모를 상황을 고려해 .scalar 대신 .scalar_one을 쓰자 
        return [_to_domain(row) for row in rows], total

    async def save(self, definition: ItemDefinition) -> ItemDefinition:

        # id가 없으면 아직 DB에 없는 아이템 카탈로그이기 때문에 행을 새로 만든다 (INSERT)
        if definition.id is None:
            row = ItemDefinitionModel(
                code=definition.code,
                name=definition.name,
                category=definition.category,
                rarity=definition.rarity,
                start_price=definition.start_price,
                description=definition.description,
                icon=definition.icon,
                weight=definition.weight,
                fishable=definition.fishable
            )
            self._session.add(row) # 세션에 저장할 것을 올린다 (아직 안 보냄)
            await self._session.flush() # 세션에 저장한 것을 DB로 보낸다 
            definition.id = row.id # DB가 받을 때 지정한 id 값을 도메인 객체에도 넣어준다 
            return definition

        # id가 있으면 이미 있는 아이템 카탈로그이기 때문에 행을 찾아 값만 바꾼다 (UPDATE)
        row = await self._session.get(ItemDefinitionModel, definition.id)
        if row is None:
            raise DefinitionNotFoundError() # id가 있는데 None이면 당연히 에러

        # 변경 가능한 속성값들만 변경시키고 (새 레코드로 옮기고) DB에 보낼 준비를 한다 
        row.start_price = definition.start_price
        row.weight = definition.weight
        row.icon = definition.icon
        row.fishable = definition.fishable
        row.description = definition.description
        # DB에 flush / commit은 서비스가 한다 
        await self._session.flush()
        return definition

    # 해당 아이템 카탈로그를 가진 아이템이 몇 개인지 센다 (관리자가 바라볼 때)
    async def count_items(self, definition_id: int) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(InventoryItemModel)
            .where(InventoryItemModel.item_definition_id == definition_id)
        )
        return result.scalar_one() 
        # scalar_one(): 1행 1열의 값을 꺼낸다. count_item은 항상 1행이라서 맞다

    async def delete(self, definition: ItemDefinition) -> None:
        result = await self._session.execute(
            delete(ItemDefinitionModel).where(ItemDefinitionModel.id == definition.id)
        )
        if result.rowcount == 0: # 지워진 행 수가 0이면 지울 행이 없는 상황 = 지울 건 다 지웠다
            raise DefinitionNotFoundError()
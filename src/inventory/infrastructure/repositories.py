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
- InventoryItemRepository는 개별 아이템을 읽고 저장한다. 아이템은 카탈로그와 함께 한 번에 읽어 InventoryItem으로 돌려준다
- find_by_id_for_update는 아이템 행만 잠그고(카탈로그 행은 잠그지 않는다) 잠금은 commit이나 rollback 때 풀린다
- save는 pop_events()로 꺼낸 이력의 시각을 도메인이 정한 값 그대로 저장한다. 저장이 실패하면 그 객체로 다시 저장하지 않고 새로 읽는다
- 이력 조회는 오래된 순이다
"""

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.domain.enums import ItemEventType, ItemOrigin, ItemRarity, ItemStatus
from inventory.domain.exceptions import DefinitionNotFoundError, ItemNotFoundError
from inventory.domain.inventory_item import InventoryItem
from inventory.domain.item_definition import ItemDefinition
from inventory.domain.item_event import ItemEvent
# 테이블 모델은 이 파일 안에서만 쓰고 밖으로는 ItemDefinition(도메인 객체)만 내보낸다
from inventory.infrastructure.models import (
    InventoryItemModel,
    ItemDefinitionModel,
    ItemEventModel
)


# === 아이템 카탈로그 레포지토리 ===

# [아이템 카탈로그 정렬] 희귀도를 글자 순서가 아니라 순위로 정렬
_RARITY_RANK = case(
    {rarity.value: rank for rank, rarity in enumerate(ItemRarity, start=1)},
    value=ItemDefinitionModel.rarity
)

# [아이템 카탈로그 정렬] 페이지마다 정렬이 엉키지 않도록 함
_SORTS = {
    'rarity_desc': (_RARITY_RANK.desc(), ItemDefinitionModel.name, ItemDefinitionModel.id),
    'name_asc': (ItemDefinitionModel.name, ItemDefinitionModel.id)
}

# [아이템 카탈로그 객체] 레코드 하나가 아이템 카탈로그 도메인 객체
def _to_domain(row: ItemDefinitionModel) -> ItemDefinition:
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

# [아이템 카탈로그] 저장소 CRUD 함수 정의
class ItemDefinitionRepository:

    # 세션은 서비스가 만들어 넘겨 준다 (같은 세션이면 한 트랜잭션으로 묶인다)
    def __init__(self, session: AsyncSession) -> None:
        self._session = session


    # [조회] 기본키(id)로 도메인 객체를 조회
    async def find_by_id(self, definition_id: int) -> ItemDefinition | None:
        row = await self._session.get(ItemDefinitionModel, definition_id)
        return None if row is None else _to_domain(row)
    

    # [조회] 코드(code)로 도메인 객체를 조회
    # → 코드(code)는 기본키가 아니기 때문에 session.get 대신 select 사용
    async def find_by_code(self, code: str) -> ItemDefinition | None:
        result = await self._session.execute(
            select(ItemDefinitionModel).where(ItemDefinitionModel.code == code)
        )
        row = result.scalar_one_or_none() # code는 unique이기 때문에 one_or_none
        return None if row is None else _to_domain(row)


    # [조회] 페이지 기준으로 목록 내역 및 total 조회
    async def find_all(
        # 별표 뒤의 인자는 이름을 붙여야만 넘길 수 있다 (값이 엉뚱하게 들어가지 않도록)
        self, *, category=None, rarity=None, sort='rarity_desc', page=1, size=20
    ) -> tuple[list[ItemDefinition], int]:

        # 1. 조건 초기화, 조건이 있으면 조건부 조회 + 조건이 없으면 전체 조회 
        conditions = []
        if category is not None:
            conditions.append(ItemDefinitionModel.category == category)
        if rarity is not None:
            conditions.append(ItemDefinitionModel.rarity == rarity)

        # 2. total 조회 (총 몇 페이지가 나올지 프론트가 판단할 때 사용 가능)
        total = (
            await self._session.execute(
                select(func.count()).select_from(ItemDefinitionModel).where(*conditions)
            )
        ).scalar_one()  # scalar_one(): 1행 1열의 값을 꺼낸다. total은 항상 1행이라서 맞다

        # 3. 목록 내역 조회
        rows = (
            await self._session.execute(
                select(ItemDefinitionModel)
                .where(*conditions)
                # 모르는 sort 값이 오면 오류 발생 → 정렬 강제 성격 재확인
                .order_by(*_SORTS[sort])
                .limit(size) # 한 페이지에서 몇 개를 받을 건지
                .offset((page-1) * size) # 앞 페이지에서 받은 만큼 건너뛴다
            )
        ).scalars() # 목록이니까 .scalars() 
        return [_to_domain(row) for row in rows], total


    # [추가] 도메인 객체 추가
    async def save(self, definition: ItemDefinition) -> ItemDefinition:

        # (INSERT) id가 없으면 아직 DB에 없는 레코드이기 때문에 행을 새로 만든다 
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

        # (UPDATE) id가 있으면 이미 있는 레코드이기 때문에 행을 찾아 값만 바꾼다 
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


    # [조회] 특정 아이템 카탈로그를 가진 아이템 개수 
    async def count_items(self, definition_id: int) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(InventoryItemModel)
            .where(InventoryItemModel.item_definition_id == definition_id)
        )
        return result.scalar_one() 
        # scalar_one(): 1행 1열의 값을 꺼낸다. count_item은 항상 1행


    # [삭제] 도메인 객체 삭제
    async def delete(self, definition: ItemDefinition) -> None:
        result = await self._session.execute(
            delete(ItemDefinitionModel).where(ItemDefinitionModel.id == definition.id)
        )
        if result.rowcount == 0: # 지워진 행 수가 0 = 지울 행이 없다 = 지울 건 다 지웠다
            raise DefinitionNotFoundError()



# === 개별 아이템 및 아이템 이력 레포지토리 ===

# [개별 아이템 정렬] 각 항목의 마지막 id로 페이지 이동 시 정렬 규칙 유지
_ITEM_SORTS = {
    # 최신 획득
    'acquired_desc': (InventoryItemModel.acquired_at.desc(), InventoryItemModel.id.desc()),
    # 희귀도 순
    'rarity_desc': (_RARITY_RANK.desc(), ItemDefinitionModel.name, InventoryItemModel.id),
    # 카탈로그 기준
    'name_asc': (ItemDefinitionModel.name, InventoryItemModel.id)
}

# [개별 아이템 정렬] 아이템과 카탈로그를 잇는 JOIN 조건
_WITH_DEFINITION = InventoryItemModel.item_definition_id == ItemDefinitionModel.id

# [개별 아이템 객체] 아이템 행 + 아이템 카탈로그 행 조합이 도메인 객체
def _item_to_domain(item_row: InventoryItemModel, definition_row: ItemDefinitionModel) -> InventoryItemModel:
    return InventoryItem(
        definition=_to_domain(definition_row),
        owner_id=item_row.owner_id,
        status=ItemStatus(item_row.status),
        origin=ItemOrigin(item_row.origin),
        acquired_at=item_row.acquired_at,
        resale_available_at=item_row.resale_available_at,
        id=item_row.id
    )

# [아이템 이력 객체] 레코드 하나가 아이템 이력 도메인 객체
def _event_to_domain(row: ItemEventModel) -> ItemEvent:
    return ItemEvent(
        event_type=ItemEventType(row.event_type),
        from_owner_id=row.from_owner_id,
        to_owner_id=row.to_owner_id,
        created_at=row.created_at,
        actor_id=row.actor_id,
        listing_id=row.listing_id,
        trade_id=row.trade_id
    )

# [개별 아이템 및 아이템 이력] 저장소 CRUD 함수 정의
class InventoryItemRepository:

    # 세션은 서비스가 만들어 넘겨 준다 (같은 세션이면 한 트랜잭션으로 묶인다)
    def __init__(self, session: AsyncSession) -> None:
        self._session = session


    # 개별 아이템 도메인 객체를 가져오는 select문
    def _select_items(self):
        return select(InventoryItemModel, ItemDefinitionModel).join(
            ItemDefinitionModel, _WITH_DEFINITION
        )


    # [조회] 개별 아이템 상태 조회
    async def _find_one(self, item_id: int, for_update: bool) -> InventoryItem | None:
        statement = self._select_items().where(InventoryItemModel.id == item_id)    

        # 개별 아이템을 조회하는 동안에는 비관적 락 / 조회 중에 상태가 변경되면 안되니까 
        if for_update:
            statement = statement.with_for_update(of=InventoryItemModel)
        # 개별 아이템은 unique이기 때문에 그 아이템의 상태도 one_or_none 
        row = (await self._session.execute(statement)).one_or_none()
        # 상태 값이 있으면 개별 아이템 도메인 객체 언팩
        return None if row is None else _item_to_domain(*row)


    # [조회] 개별 아이템 단순 조회
    async def find_by_id(self, item_id: int) -> InventoryItem | None:
        return await self._find_one(item_id, for_update=False)


    # [조회] 개별 아이템 잠금 조회
    # → 상태 변화가 일어날 것 같은 상황에서 조회 = 매물 도메인이 상태를 변경하기 위해 조회
    async def find_by_for_update(self, item_id: int) -> InventoryItem | None:
        return await self._find_one(item_id, for_update=True)


    # [조회] 특정 소유자의 아이템 목록 조회
    async def find_by_owner(
        self,
        owner_id: int,
        *,
        status=None,
        category=None,
        rarity=None,
        sort='acquired_desc',
        page=1,
        size=20,
    ) -> tuple[list[InventoryItem], int]:

        # 1. 조건 초기화, 특정 소유자의 아이템 목록이기 때문에 owner_id는 무조건 있어야 한다
        conditions = [InventoryItemModel.owner_id == owner_id]

        # 2. 개별 아이템 도메인은 행조합 객체이기 때문에 join 필요
        if status is not None:
            conditions.append(InventoryItemModel.status == status)
        if category is not None:
            conditions.append(ItemDefinitionModel.category == category)
        if rarity is not None:
            conditions.append(ItemDefinitionModel.rarity == rarity)

        # 3. total 조회 (총 몇 페이지가 나올지 프론트가 판단할 때 사용 가능)
        total = (
            await self._session.execute(
                select(func.count())
                .select_from(InventoryItemModel)
                .join(ItemDefinitionModel, _WITH_DEFINITION)
                .where(*conditions)
            )
        ).scalar_one()

        # 4. 목록 내역 조회
        rows = (
            await self._session.execute(
                self._select_items()
                .where(*conditions)
                .order_by(*_ITEM_SORTS[sort])
                .limit(size)
                .offset((page-1)*size)
            )
        ).all() # 개별 아이템은 행조합 객체이기 때문에 all로 다 받는다 
        return [_item_to_domain(item_row, definition_row) for item_row, definition_row in rows], total


    # [추가] 개별 아이템 및 아이템 이력 도메인 객체 추가
    async def save(self, item:InventoryItem) -> InventoryItem:

        # (INSERT) id가 없으면 아직 DB에 없는 레코드이기 때문에 행을 새로 만든다
        if item.id is None:
            row = InventoryItemModel(
                item_definition_id=item.definition.id,
                owner_id=item.owner_id,
                status=item.status,
                origin=item.origin,
                acquired_at=item.acquired_at,
                resale_available_at=item.resale_available_at,
            )
            self._session.add(row)
            # 아이템 이력 도메인 객체가 item.id를 가리켜야 하므로 먼저 flush
            await self._session.flush()
            item.id = row.id

        # (UPDATE) id가 있으면 이미 있는 레코드이기 때문에 행을 찾아 값만 바꾼다 
        else:
            row = await self._session.get(InventoryItemModel, item.id)
            if row is None:
                raise ItemNotFoundError()
            row.owner_id=item.owner_id
            row.status=item.status
            row.origin=item.origin
            row.acquired_at=item.acquired_at
            row.resale_available_at=item.resale_available_at
            row.updated_at=func.now()

        # (INSERT) 아이템에 그동안 쌓인 이력을 꺼내서 추가 / item_event 도메인 참조
        for event in item.pop_events():
            self._session.add(
                ItemEventModel(
                    item_id=item.id,
                    event_type=event.event_type,
                    from_owner_id=event.from_owner_id,
                    to_owner_id=event.to_owner_id,
                    actor_id=event.actor_id,
                    listing_id=event.listing_id,
                    trade_id=event.trade_id,
                    created_at=event.created_at,
                )
            )
            await self._session.flush() # DB에 flush / commit은 서비스가 한다 
            return item


        # [조회] 아이템 이력 목록 조회 (오래된순)
        async def find_events(
            self, item_id: int, *, page=1, size=20
        ) -> tuple[list[ItemEvent], int]:
            
            # 1. total 조회 (총 몇 페이지가 나올지 프론트가 판단할 때 사용 가능)
            total = (
                await self._session.execute(
                    select(func.count())
                    .select_from(ItemEventModel)
                    .where(ItemEventModel.item_id == item_id)
                )
            ).scalar_one()

            # 2. 목록 내역 조회
            rows = (
                await self._session.execute(
                    select(ItemEventModel)
                    .where(ItemEventModel.item_id == item_id)
                    .order_by(ItemEventModel.created_at, ItemEventModel.id)
                    .limit(size)
                    .offset((page-1)*size)
                )
            ).scalars()
            return [_event_to_domain(row) for row in rows], total


        # [조회] 특정 소유자의 판매 예약 아이템 조회 (회원탈퇴 점검용)
        async def has_listed_items(self, owner_id: int) -> bool:
            result = await self._session.execute(
                select(
                    exists().where(
                        InventoryItemModel.owner_id == owner_id,
                        InventoryItemModel.status == ItemStatus.LISTED,
                    )
                )
            )
            return result.scalar_one()
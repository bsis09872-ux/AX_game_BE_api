"""인벤토리의 부품 조립: 계약에 맞는 어댑터를 만들어 돌려준다

- 다른 도메인의 wiring을 이용해 어댑터를 조립한다 (다른 도메인의 infrastructure를 직접 import하지 않는다)
- 세션은 호출자가 만들고 닫는다 (같은 세션이면 한 트랜잭션으로 묶인다)
- 업무 규칙을 두지 않는다
"""

from sqlalchemy.ext.asyncio import AsyncSession

from inventory.application.contracts import UserLookup, CurrentUserProvider
from inventory.application.service import InventoryService

from inventory.infrastructure.repositories import (
    InventoryItemRepository,
    ItemDefinitionRepository
)
from inventory.infrastructure.unit_of_work import SqlAlchemyUnitOfWork
from inventory.infrastructure.user_lookup import UserLookupAdapter
from inventory.infrastructure.current_user import CurrentUserAdapter

from auth.wiring import build_auth_service
from users.wiring import build_user_service

# 반환 타입은 계약에서 정한 바와 같다 
def build_user_lookup(session: AsyncSession) -> UserLookup:
    return UserLookupAdapter(user_service=build_user_service(session=session))

# 서비스 돌아가게 하기
def build_inventory_service(session: AsyncSession) -> InventoryService:
    return InventoryService(
        items=InventoryItemRepository(session),
        definitions=ItemDefinitionRepository(session),
        user_lookup=build_user_lookup(session),
        unit_of_work=SqlAlchemyUnitOfWork(session)
    )

# auth가 토큰으로 요청한 사람을 확인하는 기능
def build_current_user_provider(session: AsyncSession) -> CurrentUserProvider:
    return CurrentUserAdapter(
        auth_service=build_auth_service(session),
        user_service=build_user_service(session=session),
    )

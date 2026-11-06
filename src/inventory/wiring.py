"""인벤토리의 부품 조립: 계약에 맞는 어댑터를 만들어 돌려준다

- 다른 도메인의 wiring을 이용해 어댑터를 조립한다 (다른 도메인의 infrastructure를 직접 import하지 않는다)
- 세션은 호출자가 만들고 닫는다 (같은 세션이면 한 트랜잭션으로 묶인다)
- 업무 규칙을 두지 않는다
"""

from sqlalchemy.ext.asyncio import AsyncSession

from inventory.application.contracts import UserLookup
from inventory.user_lookup import UserLookupAdapter

# 이걸 쓰면 users의 infrastructure를 몰라도 된다 
from users.wiring import build_user_service

# 반환 타입은 계약에서 정한 바와 같다 
def build_user_lookup(session: AsyncSession) -> UserLookup:
    return UserLookupAdapter(user_service=build_user_service(session=session))
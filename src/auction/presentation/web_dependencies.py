# [Claude] 이 파일은 Claude가 작성함 (검토 전)
"""경매 화면이 서비스 밖에서 읽는 값의 의존성 (사용자 이름, 아이템 정보, 보유 골드)

- 다른 도메인은 그 도메인의 wiring으로만 가져온다 (auction/wiring.py가 이미 쓰는 조립 함수를 재사용)
- 화면은 읽기만 한다. 값을 바꾸는 호출은 서비스(ListingService)가 한다
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auction.wiring import build_inventory_service, build_user_gateway, build_wallet_service
from database import get_db
from shared.core.exceptions import AppError


# 사용자 번호 → 표시 이름(display_name)을 읽는 창구
def get_user_gateway(session: AsyncSession = Depends(get_db)):
    return build_user_gateway(session)


# 아이템 이름·그림·희귀도를 읽는 인벤토리 서비스
def get_inventory_reader(session: AsyncSession = Depends(get_db)):
    return build_inventory_service(session)


# 헤더에 보여 줄 보유 골드. 지갑을 잠그지 않는 조회라 어느 화면에서나 부를 수 있다
# 지갑이 없으면 None(헤더에 아무것도 안 보여 줌)
async def read_balance(session: AsyncSession, user_id: int) -> int | None:
    try:
        wallet = await build_wallet_service(session).get_wallet(user_id)
    except AppError:
        return None
    return wallet.balance.value


# 가방의 지갑 박스(잔액, 묶인 골드, 사용 가능 골드). 지갑을 잠그고 읽고, 처음 조회면 지갑이 만들어지므로 commit한다
async def read_wallet_box(session: AsyncSession, user_id: int) -> dict | None:
    try:
        view = await build_wallet_service(session).get_my_wallet(user_id)
        await session.commit()
    except AppError:
        return None
    return {'balance': view.balance, 'held': view.held_amount, 'available': view.available_balance}

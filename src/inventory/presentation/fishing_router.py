"""낚시 API 라우터 (/v1/fishing-results)

- 로그인한 사용자만 쓴다. 결과는 서버가 정하고 요청에서 받는 값은 없다
- 설정 DEMO_FISHING_ENABLED가 켜졌을 때만 앱에 등록한다 (등록은 main.py가 한다)
- 라우터는 서비스 호출과 응답 변환만 한다 (업무 판정, DB 갱신, commit을 하지 않는다)
- 쿨다운(429)과 후보 없음(503)의 응답은 팀 공통 핸들러의 분류가 생긴 뒤에 맞춘다
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends

from inventory.application.contracts import CurrentUser
from inventory.application.fishing_service import FishingService

from inventory.presentation.dependencies import get_current_user, get_fishing_service
from inventory.presentation.schemas import InventoryItemResponse

router = APIRouter(tags=['fishing'])

# 낚시 한 번: 성공하면 이력이 깔끔한 새 아이템 보상 지급
@router.post('/fishing-results', status_code=201, response_model=InventoryItemResponse)
async def go_fishing(
    user: CurrentUser = Depends(get_current_user),
    service: FishingService = Depends(get_fishing_service)
) -> InventoryItemResponse:
    item = await service.go_fishing(user.id, datetime.now(timezone.utc))
    return InventoryItemResponse.from_info(item)
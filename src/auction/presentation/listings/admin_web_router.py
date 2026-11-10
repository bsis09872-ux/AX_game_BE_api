# 관리자 웹 화면용 매물 API: HttpOnly 쿠키로 인증하는 브라우저 요청을 처리한다.
# 웹 JS는 쿠키의 토큰을 읽을 수 없어 Bearer 헤더를 만들 수 없으므로 /v1 API와 별도로 둔다.
# 인증 의존성(쿠키 인증·관리자 확인·Origin 검사)은 main.py가 auth의 것을 넘겨 준다.
# auction은 auth를 직접 import하지 않으며, 업무 흐름은 기존 ListingService를 재사용한다.

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response

from auction.presentation.dependencies import ListingServiceDep
from auction.presentation.listings.schemas import AdminCancelResponse


# 관리자 웹 화면용 라우터를 만든다.
# 입력: 쿠키로 인증된 관리자 ID를 반환하는 의존성. 반환: /admin 아래 경로를 가진 라우터.
def create_listing_admin_web_router(
    current_admin_id: Callable[..., Awaitable[int]],
) -> APIRouter:
    router = APIRouter(prefix="/admin", tags=["admin-auctions"])

    # [관리자] 웹 화면에서 매물을 강제 취소한다. 처리 규칙은 /v1 관리자 취소와 같다.
    # 입력: 매물 ID·쿠키 인증된 관리자 ID(요청 본문 없음). 반환: 안내 메시지만.
    @router.post(
        "/listings/{listing_id}/cancel",
        response_model=AdminCancelResponse,
        summary="관리자 매물 강제 취소 (웹)",
    )
    async def admin_cancel_listing_web(
        listing_id: Annotated[int, Path(ge=1, le=9223372036854775807)],
        response: Response,
        service: ListingServiceDep,
        admin_id: int = Depends(current_admin_id),
    ) -> AdminCancelResponse:
        await service.admin_cancel(
            admin_id=admin_id,
            listing_id=listing_id,
            now=datetime.now(timezone.utc),
        )
        response.headers['Cache-Control'] = 'no-store'
        return AdminCancelResponse()

    return router

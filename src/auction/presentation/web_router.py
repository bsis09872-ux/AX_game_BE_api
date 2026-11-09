# [Claude] 이 파일은 Claude가 작성함 (검토 전)
"""경매장 화면 라우터 (Jinja2)

- 로그인 확인과 출처 확인은 main에서 넘겨 받는다 (auth의 쿠키 구조를 모른다)
- 라우터는 서비스 호출과 화면 데이터 준비만 한다. 업무 판정은 서비스·도메인이 한다
- 개인 화면이라 브라우저에 저장하지 않게 한다 (Cache-Control: no-store)
- 주소 문자열은 데코레이터와 web_views.py에만 둔다 (화면 URL은 담당자 결정 대기)
- ?embed=1이면 팝업(iframe) 안의 화면이다. 헤더를 숨기고 보유 골드도 읽지 않는다
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from auction.presentation.web_dependencies import read_balance
from database import get_db


# 모든 화면이 공통으로 쓰는 요청 정보
@dataclass(frozen=True)
class PageContext:
    user_id: int
    embed: bool
    gold: int | None

    # 템플릿(_layout.html)이 쓰는 공통 값
    def base(self, nav_active: str = 'auction') -> dict:
        return {'embed': self.embed, 'gold': self.gold, 'nav_active': nav_active}


# 템플릿을 그려 응답으로 만든다. 개인 화면이라 브라우저에 저장하지 않는다
def render(request: Request, name: str, context: dict, status_code: int = 200):
    response = request.app.state.templates.TemplateResponse(
        request=request, name=name, context=context, status_code=status_code,
    )
    response.headers['Cache-Control'] = 'no-store'
    return response


def create_auction_web_router(
    current_user_id: Callable[..., Awaitable[int]],
    require_origin: Callable[..., None],
) -> APIRouter:
    router = APIRouter()

    # 로그인한 사용자와 embed 여부, 보유 골드를 한 번에 준비한다 (팝업 안에서는 헤더가 숨겨져 골드를 읽지 않는다)
    async def page_context(
        embed: bool = Query(False),
        user_id: int = Depends(current_user_id),
        session: AsyncSession = Depends(get_db),
    ) -> PageContext:
        gold = None if embed else await read_balance(session, user_id)
        return PageContext(user_id=user_id, embed=embed, gold=gold)

    # 화면 라우트는 이 아래에 단위별로 추가한다 (목록, 상세, 등록, 입찰·취소, 내 거래)

    return router

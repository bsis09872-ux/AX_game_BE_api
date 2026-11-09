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
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auction.domain.listings.entities import ListingStatus
from auction.presentation.dependencies import ListingServiceDep, TradeServiceDep
from auction.presentation.web_dependencies import get_inventory_reader, get_user_gateway, read_balance
from auction.presentation.web_views import UNKNOWN_ITEM, card_view, detail_view, item_view, list_url, notice_text
from auction.wiring import PAGE_SIZE
from database import get_db
from shared.core.exceptions import AppError, NotFoundError


# 모든 화면이 공통으로 쓰는 요청 정보
@dataclass(frozen=True)
class PageContext:
    user_id: int
    embed: bool
    gold: int | None

    # 템플릿(_layout.html)이 쓰는 공통 값
    def base(self, nav_active: str = 'auction') -> dict:
        return {'embed': self.embed, 'gold_balance': self.gold, 'nav_active': nav_active}


# 템플릿을 그려 응답으로 만든다. 개인 화면이라 브라우저에 저장하지 않는다
def render(request: Request, name: str, context: dict, status_code: int = 200):
    response = request.app.state.templates.TemplateResponse(
        request=request, name=name, context=context, status_code=status_code,
    )
    response.headers['Cache-Control'] = 'no-store'
    return response


# 아이템 정보를 읽어 화면용 값으로 만든다. 못 읽으면 "알 수 없는 아이템"으로 대신한다
async def load_item(inventory, inventory_item_id: int):
    try:
        return item_view(await inventory.get_item(inventory_item_id))
    except AppError:
        return UNKNOWN_ITEM


# 없는 매물과 남의 대기 매물은 같은 화면(404)으로 보여 준다 (존재 여부를 알려 주지 않는다)
def not_found_response(request: Request, ctx: PageContext):
    return render(request, 'auction/not_found.html', ctx.base(), status_code=404)


# 매물 상세 화면을 그린다. 입찰·취소가 실패했을 때 같은 화면에 오류를 얹어 다시 그리는 데도 쓴다
async def detail_response(
    request: Request, ctx: PageContext, listing_id: int,
    service, trades, users, inventory,
    *, notice: str | None = None, error: str | None = None, status_code: int = 200,
):
    try:
        listing = await service.get_listing_detail(listing_id)
    except NotFoundError:
        return not_found_response(request, ctx)
    # 대기 매물은 공개 전이라 판매자에게만 보인다
    if listing.status == ListingStatus.QUEUED and listing.seller_id != ctx.user_id:
        return not_found_response(request, ctx)

    now = datetime.now(timezone.utc)
    winner_id = listing.current_bidder_id if listing.status == ListingStatus.SOLD else None
    names = await users.get_display_names([listing.seller_id] + ([winner_id] if winner_id else []))

    # 입찰 제한 상태는 입찰할 수 있는 사람에게만 보여 준다 (제한 중에도 조회는 허용)
    blocked_seconds = None
    if listing.status == ListingStatus.BIDDING and listing.seller_id != ctx.user_id:
        try:
            state = await trades.get_bid_limit_status(ctx.user_id, now)
            blocked_seconds = int(state.remaining.total_seconds()) if state.is_blocked else None
        except AppError:
            blocked_seconds = None

    view = detail_view(
        listing, ctx.user_id, now,
        await load_item(inventory, listing.inventory_item_id),
        names.get(listing.seller_id, '알 수 없음'),
        names.get(winner_id, '알 수 없음') if winner_id else '',
        blocked_seconds,
        ctx.embed,
    )
    return render(request, 'auction/detail.html', {**ctx.base(), 'd': view, 'notice': notice, 'error': error}, status_code)


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

    # region [Claude] 경매장 목록
    @router.get('/auctions', response_class=HTMLResponse)
    async def get_auction_list_page(
        request: Request,
        service: ListingServiceDep,
        users=Depends(get_user_gateway),
        inventory=Depends(get_inventory_reader),
        page: int = Query(1, ge=1),
        ctx: PageContext = Depends(page_context),
    ):
        listings = await service.get_listing_list(page)
        now = datetime.now(timezone.utc)
        names = await users.get_display_names([listing.seller_id for listing in listings])

        # shortcut: 매물마다 아이템을 한 번씩 읽는다(N번 조회). 아이템 일괄 조회가 열리면 한 번으로 줄인다
        cards = [
            card_view(
                listing,
                await load_item(inventory, listing.inventory_item_id),
                names.get(listing.seller_id, '알 수 없음'),
                now,
                ctx.embed,
            )
            for listing in listings
        ]
        # shortcut: 남은 시간 순 정렬은 이 쪽 안에서만 맞다(저장소는 공개 시각 최신순). 진행 매물은 아이템 종류당 1개라 대부분 한 쪽에 다 들어간다
        cards.sort(key=lambda card: card.remaining_seconds)

        return render(request, 'auction/index.html', {
            **ctx.base(),
            'cards': cards,
            'has_previous': page > 1,
            # 전체 개수를 모르므로 꽉 찬 쪽이면 다음 쪽이 있다고 본다
            'has_next': len(listings) == PAGE_SIZE,
            'prev_url': list_url(page - 1, ctx.embed),
            'next_url': list_url(page + 1, ctx.embed),
        })
    # endregion

    # region [Claude] 경매 상세 (진행, 낙찰, 유찰, 취소, 대기 모두 이 화면)
    # {listing_id:int}는 숫자만 받아서 /auctions/new 같은 고정 주소와 겹치지 않는다
    @router.get('/auctions/{listing_id:int}', response_class=HTMLResponse)
    async def get_auction_detail_page(
        request: Request,
        service: ListingServiceDep,
        trades: TradeServiceDep,
        listing_id: int = Path(ge=1),
        users=Depends(get_user_gateway),
        inventory=Depends(get_inventory_reader),
        ok: str | None = None,
        ctx: PageContext = Depends(page_context),
    ):
        return await detail_response(
            request, ctx, listing_id, service, trades, users, inventory, notice=notice_text(ok),
        )
    # endregion

    return router

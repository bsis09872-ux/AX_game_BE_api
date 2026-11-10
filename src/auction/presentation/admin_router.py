from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import HTMLResponse

from auction.application.admin_queries import AdminAuctionQueries
from auction.presentation.admin_queries import AdminListingQuery, AdminTradeQuery
from shared.core.exceptions import NotFoundError
from users.application.service import UserService
from users.presentation.dependencies import get_user_service
from users.presentation.schemas import UserMeResponse


def create_admin_auction_router(current_admin_id, reader_dependency) -> APIRouter:
    router = APIRouter(prefix='/admin', tags=['admin-auctions'])

    async def render(request, users, actor_id, template, section, context, *, status=200):
        actor = UserMeResponse.from_user(await users.get_user(actor_id))
        return request.app.state.templates.TemplateResponse(
            request=request, name=f'admin/{template}.html', status_code=status,
            context={'user': actor, 'section': section, **context},
            headers={'Cache-Control': 'no-store'},
        )

    @router.get('/auctions', response_class=HTMLResponse)
    async def auctions(
        request: Request,
        query: Annotated[AdminListingQuery, Query()],
        actor_id: int = Depends(current_admin_id),
        users: UserService = Depends(get_user_service),
        reader: AdminAuctionQueries = Depends(reader_dependency),
    ):
        rows, has_next = await reader.list_listings(actor_id, query.page, **query.filters())
        return await render(request, users, actor_id, 'auctions', 'auctions', {
            'rows': rows, 'query': query, 'has_next': has_next,
        })

    @router.get('/auctions/{listing_id}', response_class=HTMLResponse)
    async def auction_detail(
        request: Request,
        listing_id: Annotated[int, Path(ge=1, le=9223372036854775807)],
        query: Annotated[AdminListingQuery, Query()],
        actor_id: int = Depends(current_admin_id),
        users: UserService = Depends(get_user_service),
        reader: AdminAuctionQueries = Depends(reader_dependency),
    ):
        selected, status = None, 200
        try:
            selected = await reader.get_listing(actor_id, listing_id)
        except NotFoundError:
            status = 404

        # 목록의 조건만 보존해 돌아간다. 외부 URL을 복귀 주소로 받지 않는다.
        return await render(request, users, actor_id, 'auction_detail', 'auctions', {
            'selected': selected, 'listing_id': listing_id,
            'back_url': query.page_url('/admin/auctions'),
        }, status=status)

    @router.get('/auction-trades', response_class=HTMLResponse)
    async def auction_trades(
        request: Request,
        query: Annotated[AdminTradeQuery, Query()],
        actor_id: int = Depends(current_admin_id),
        users: UserService = Depends(get_user_service),
        reader: AdminAuctionQueries = Depends(reader_dependency),
    ):
        rows, has_next = await reader.list_trades(actor_id, query.page, **query.filters())
        return await render(request, users, actor_id, 'auction_trades', 'trades', {
            'rows': rows, 'query': query, 'has_next': has_next,
        })

    return router

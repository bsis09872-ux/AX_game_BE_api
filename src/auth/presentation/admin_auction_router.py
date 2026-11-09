from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from auth.application.admin_contracts import AdminAuctionReader
from auth.presentation.web_dependencies import get_current_web_admin_id
from shared.core.exceptions import NotFoundError
from users.application.service import UserService
from users.presentation.dependencies import get_user_service
from users.presentation.schemas import UserMeResponse


def create_admin_auction_router(reader_dependency) -> APIRouter:
    router = APIRouter(prefix='/admin', tags=['admin-auctions'])

    @router.get('/auctions', response_class=HTMLResponse)
    async def auctions(request: Request, page: int = Query(1, ge=1, le=2147483647),
                       listing_id: int | None = Query(None, ge=1, le=9223372036854775807),
                       actor_id: int = Depends(get_current_web_admin_id),
                       users: UserService = Depends(get_user_service),
                       reader: AdminAuctionReader = Depends(reader_dependency)):
        selected, rows, has_next, status = None, [], False, 200
        if listing_id is None:
            rows, has_next = await reader.list_bidding(page)
        else:
            try:
                selected = await reader.get_listing(listing_id)
            except NotFoundError:
                status = 404
        actor = UserMeResponse.from_user(await users.get_user(actor_id))
        return request.app.state.templates.TemplateResponse(
            request=request, name='auth/admin/auctions.html', status_code=status,
            context={'user': actor, 'section': 'auctions', 'rows': rows,
                     'selected': selected, 'listing_id': listing_id,
                     'page': page, 'has_next': has_next},
            headers={'Cache-Control': 'no-store'},
        )

    return router

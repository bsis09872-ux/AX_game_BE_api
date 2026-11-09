from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from fastapi.responses import HTMLResponse

from users.application.service import UserService
from users.presentation.dependencies import get_user_service
from users.presentation.schemas import UserMeResponse
from users.presentation.admin_schemas import AdminMemberResponse
from users.presentation.admin_schemas import AdminMemberCreateRequest, AdminMemberRoleRequest
from users.presentation.admin_schemas import AdminLoginSuspensionRequest
from users.presentation.admin_schemas import AdminBidRestrictionRequest
from users.application.admin_service import MemberAdminService


def create_member_admin_router(current_admin_id, management_dependency) -> APIRouter:
    router = APIRouter(prefix='/admin', tags=['admin-members'])

    async def render(request, users, actor_id, template, **context):
        actor = UserMeResponse.from_user(await users.get_user(actor_id))
        return request.app.state.templates.TemplateResponse(
            request=request, name=f'auth/admin/{template}.html',
            context={'user': actor, 'section': 'members', **context},
            headers={'Cache-Control': 'no-store'},
        )

    @router.get('/members', response_class=HTMLResponse)
    async def members(request: Request, q: str = Query('', max_length=100),
                      role: Literal['', 'USER', 'ADMIN'] = '',
                      page: int = Query(1, ge=1),
                      actor_id: int = Depends(current_admin_id),
                      users: UserService = Depends(get_user_service)):
        rows, total = await users.list_members(q.strip(), role or None, page, 20)
        return await render(request, users, actor_id, 'members',
                            members=[AdminMemberResponse.from_user(row) for row in rows],
                            q=q, role=role, page=page, total=total, pages=max(1, (total + 19) // 20))

    @router.get('/members/new', response_class=HTMLResponse)
    async def new_member(request: Request, actor_id: int = Depends(current_admin_id),
                         users: UserService = Depends(get_user_service)):
        return await render(request, users, actor_id, 'member_create')

    @router.post('/member-accounts', response_model=AdminMemberResponse, status_code=201)
    async def create_member(body: AdminMemberCreateRequest, response: Response,
                            actor_id: int = Depends(current_admin_id),
                            management: MemberAdminService = Depends(management_dependency)):
        member = await management.create_account(actor_id, **body.model_dump())
        response.headers['Cache-Control'] = 'no-store'
        return AdminMemberResponse.from_user(member)

    @router.patch('/member-accounts/{member_id}/role', response_model=AdminMemberResponse)
    async def change_role(body: AdminMemberRoleRequest, response: Response, member_id: int = Path(ge=1),
                          actor_id: int = Depends(current_admin_id),
                          management: MemberAdminService = Depends(management_dependency)):
        member = await management.change_role(actor_id, member_id, body.role)
        response.headers['Cache-Control'] = 'no-store'
        return AdminMemberResponse.from_user(member)

    @router.patch('/member-accounts/{member_id}/login-suspension', response_model=AdminMemberResponse)
    async def suspend_login(body: AdminLoginSuspensionRequest, response: Response, member_id: int = Path(ge=1),
                            actor_id: int = Depends(current_admin_id),
                            management: MemberAdminService = Depends(management_dependency)):
        member = await management.set_login_suspension(actor_id, member_id, body.suspended)
        response.headers['Cache-Control'] = 'no-store'
        return AdminMemberResponse.from_user(member)

    @router.patch('/member-accounts/{member_id}/bid-restriction', response_model=AdminMemberResponse)
    async def restrict_bidding(body: AdminBidRestrictionRequest, response: Response, member_id: int = Path(ge=1),
                               actor_id: int = Depends(current_admin_id),
                               management: MemberAdminService = Depends(management_dependency)):
        member = await management.set_bid_restriction(actor_id, member_id, body.until)
        response.headers['Cache-Control'] = 'no-store'
        return AdminMemberResponse.from_user(member)

    @router.get('/members/{member_id}', response_class=HTMLResponse)
    async def member_detail(request: Request, member_id: int = Path(ge=1),
                            actor_id: int = Depends(current_admin_id),
                            users: UserService = Depends(get_user_service)):
        return await render(request, users, actor_id, 'member_detail',
                            member=AdminMemberResponse.from_user(await users.get_user(member_id)))

    return router

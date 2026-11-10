"""여러 도메인 화면의 진입점. 인증 의존성은 앱에서 주입한다."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from users.application.service import UserService
from users.presentation.dependencies import get_user_service
from users.presentation.schemas import UserMeResponse


def create_dashboard_router(current_admin_id) -> APIRouter:
    router = APIRouter()

    @router.get('/admin', response_class=HTMLResponse, tags=['admin-web'])
    async def dashboard(
        request: Request,
        user_id: int = Depends(current_admin_id),
        users: UserService = Depends(get_user_service),
    ):
        user = UserMeResponse.from_user(await users.get_user(user_id))
        return request.app.state.templates.TemplateResponse(
            request=request, name='admin/home.html',
            context={'user': user, 'section': 'home'},
            headers={'Cache-Control': 'no-store'},
        )

    return router

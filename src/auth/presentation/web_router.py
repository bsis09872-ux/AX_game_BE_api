from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from auth.application.service import AuthService
from auth.domain.exceptions import AuthenticationError
from auth.presentation.dependencies import get_auth_service
from auth.presentation.web_dependencies import (
    clear_auth_cookies,
    require_web_origin,
    set_auth_cookies,
)

router = APIRouter()


def login_page(request: Request, *, error: str = "", status_code: int = 200):
    response = request.app.state.templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={
            "error": error,
            "resume": bool(request.cookies.get("refresh_token")) and not error,
        },
        status_code=status_code,
    )

    response.headers["Cache-Control"] = "no-store"

    return response


@router.get("/login", response_class=HTMLResponse)
async def get_login(request: Request):
    return login_page(request)


@router.post("/login", dependencies=[Depends(require_web_origin)])
async def login(
    request: Request,
    login_id: str = Form(..., min_length=4, max_length=50),
    password: str = Form(..., min_length=1, max_length=1024),
    service: AuthService = Depends(get_auth_service),
):
    try:
        tokens = await service.login(login_id, password)
    except AuthenticationError:
        return login_page(
            request,
            error="로그인 ID 또는 비밀번호를 확인해 주세요.",
            status_code=401,
        )

    response = RedirectResponse("/me", status_code=303)
    set_auth_cookies(response, tokens)

    return response


@router.get("/session")
async def session_status(
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    claims = await service.authenticate(request.cookies.get("access_token", ""))

    return JSONResponse(
        {
            "expires_in": max(
                0,
                int((claims.expires_at - datetime.now(timezone.utc)).total_seconds()),
            ),
        },
        headers={"Cache-Control": "no-store"},
    )


@router.post("/session/refresh", dependencies=[Depends(require_web_origin)])
async def refresh(
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    try:
        tokens = await service.refresh(request.cookies.get("refresh_token", ""))
    except AuthenticationError:
        response = JSONResponse({"detail": "로그인이 필요합니다."}, status_code=401)
        clear_auth_cookies(response)

        return response

    response = JSONResponse({"expires_in": tokens.expires_in})
    set_auth_cookies(response, tokens)

    return response


@router.post("/logout", dependencies=[Depends(require_web_origin)])
async def logout(
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    refresh_token = request.cookies.get("refresh_token")
    access_token = request.cookies.get("access_token")

    if refresh_token:
        try:
            await service.logout_session(refresh_token)
        except AuthenticationError:
            pass

    if access_token:
        try:
            await service.logout(access_token)
        except AuthenticationError:
            pass

    response = RedirectResponse("/login", status_code=303)
    clear_auth_cookies(response)

    return response

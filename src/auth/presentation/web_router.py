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
    # 쿠키가 있어도 인증 성공으로 판단하지 않는다. 화면에서 서버에 복구를 요청한다.
    # 로그인 입력 오류가 있으면 자동 이동보다 오류 안내를 우선한다.
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
    # 로그인 폼과 기존 쿠키의 인증 복구 화면을 함께 제공한다.
    return login_page(request)


@router.post("/login", dependencies=[Depends(require_web_origin)])
async def login(
    request: Request,
    login_id: str = Form(..., min_length=4, max_length=50),
    password: str = Form(..., min_length=1, max_length=1024),
    service: AuthService = Depends(get_auth_service),
):
    # 로그인 검증과 세션 발급은 서비스에 맡기고 웹 응답만 구성한다.
    try:
        tokens = await service.login(login_id, password)
    except AuthenticationError:
        return login_page(
            request,
            error="로그인 ID 또는 비밀번호를 확인해 주세요.",
            status_code=401,
        )

    # 폼 제출 후 새로고침해도 로그인 POST를 다시 보내지 않도록 GET /me로 이동한다.
    response = RedirectResponse("/me", status_code=303)
    set_auth_cookies(response, tokens)

    return response


@router.get("/session")
async def session_status(
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    # 서명, 만료, 세션 폐기와 활성 회원 여부를 검증하고 갱신 예약용 시간만 반환한다.
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
    # refresh token 검증/회전은 서버가 수행한다. 실패하면 더 이상 쓸 수 없는 쿠키를 지운다.
    try:
        tokens = await service.refresh(request.cookies.get("refresh_token", ""))
    except AuthenticationError:
        response = JSONResponse({"detail": "로그인이 필요합니다."}, status_code=401)
        clear_auth_cookies(response)

        return response

    # JavaScript에는 남은 시간만 공개하고 새 토큰은 HttpOnly 쿠키로 전달한다.
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

    # access가 만료돼도 refresh cookie로 현재 로그인 세션을 폐기할 수 있다.
    if refresh_token:
        try:
            await service.logout_session(refresh_token)
        except AuthenticationError:
            pass

    # 남아 있는 access token도 폐기한다. 이전 버전의 세션 ID 없는 토큰도 처리한다.
    if access_token:
        try:
            await service.logout(access_token)
        except AuthenticationError:
            pass

    # 인증 실패는 이미 로그아웃된 상태로 처리하지만 DB 장애 등은 위에서 전파된다.
    response = RedirectResponse("/login", status_code=303)
    clear_auth_cookies(response)

    return response

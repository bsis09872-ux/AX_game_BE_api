from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import ValidationError

from auth.application.service import AuthService
from auth.domain.exceptions import AuthenticationError
from auth.presentation.dependencies import get_auth_service
from auth.presentation.schemas import RegisterUserRequest
from auth.presentation.web_dependencies import (
    clear_auth_cookies,
    require_web_origin,
    set_auth_cookies,
)
from shared.core.exceptions import BusinessRuleError, ConflictError

router = APIRouter()


def login_page(request: Request, *, error: str = "", status_code: int = 200):
    # 쿠키가 있어도 인증 성공으로 판단하지 않는다. 화면에서 서버에 복구를 요청한다.
    # 오류, 가입 완료, 세션 만료 안내가 있으면 이전 쿠키로 자동 복구하지 않는다.
    registered = request.query_params.get("registered") == "1"
    expired = request.query_params.get("expired") == "1"

    response = request.app.state.templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={
            "error": error or (
                "로그인 시간이 만료됐습니다. 다시 로그인해 주세요." if expired else ""
            ),
            "registered": registered,
            "resume": bool(request.cookies.get("refresh_token"))
            and not (error or registered or expired),
        },
        status_code=status_code,
    )

    response.headers["Cache-Control"] = "no-store"

    return response


def register_page(
    request: Request,
    *,
    error: str = "",
    login_id: str = "",
    display_name: str = "",
    status_code: int = 200,
):
    # 실패한 입력 중 ID와 표시 이름만 복원한다. 비밀번호는 context에 전달하지 않는다.
    response = request.app.state.templates.TemplateResponse(
        request=request,
        name="auth/register.html",
        context={
            "error": error,
            "login_id": login_id,
            "display_name": display_name,
        },
        status_code=status_code,
    )

    response.headers["Cache-Control"] = "no-store"

    return response


@router.get("/register", response_class=HTMLResponse)
async def get_register(request: Request):
    return register_page(request)


@router.post("/register", dependencies=[Depends(require_web_origin)])
async def register(
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    # API와 같은 입력 스키마로 검증한다. 추가 필드나 HTML 제한을 우회한 요청도 거절한다.
    async with request.form(max_files=0) as form:
        values = dict(form)

    public_values = {
        name: values[name][:50] if isinstance(values.get(name), str) else ""
        for name in ("login_id", "display_name")
    }

    try:
        signup = RegisterUserRequest.model_validate(values)
    except ValidationError as exc:
        # 검증 예외에 들어 있는 비밀번호 원문 대신 미리 정한 안내만 공개한다.
        field = exc.errors(include_input=False)[0]["loc"][0]
        messages = {
            "login_id": "로그인 ID는 소문자, 숫자, 밑줄로 4~50자를 입력해 주세요.",
            "display_name": "표시 이름은 공백이 아닌 문자를 포함해 2~50자를 입력해 주세요.",
            "password": "비밀번호는 1~1024자를 입력해 주세요.",
        }

        return register_page(
            request,
            error=messages.get(field, "허용되지 않은 입력 항목이 있습니다."),
            status_code=422,
            **public_values,
        )

    # 기존 가입 서비스가 해싱, 회원 생성과 commit을 담당한다.
    try:
        await service.register_user(
            login_id=signup.login_id,
            display_name=signup.display_name,
            password=signup.password,
        )
    except ConflictError as exc:
        return register_page(request, error=exc.message, status_code=409, **public_values)
    except BusinessRuleError as exc:
        return register_page(request, error=exc.message, status_code=400, **public_values)

    # 가입 POST가 새로고침으로 반복되지 않도록 로그인 화면으로 이동한다.
    return RedirectResponse(
        "/login?registered=1",
        status_code=303,
        headers={"Cache-Control": "no-store"},
    )


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
    now = datetime.now(timezone.utc)
    session_expires_at = claims.session_expires_at

    return JSONResponse(
        {
            "expires_in": max(
                0,
                int((claims.expires_at - now).total_seconds()),
            ),
            "session_expires_in": max(0, (session_expires_at - now).total_seconds()),
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
    response = JSONResponse({
        "expires_in": tokens.expires_in,
        "session_expires_in": tokens.refresh_expires_in,
    })
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

    # access cookie만 남아 있어도 연결된 로그인 세션을 폐기한다.
    if access_token:
        try:
            await service.logout(access_token)
        except AuthenticationError:
            pass

    # 인증 실패는 이미 로그아웃된 상태로 처리하지만 DB 장애 등은 위에서 전파된다.
    response = RedirectResponse("/login", status_code=303)
    clear_auth_cookies(response)

    return response

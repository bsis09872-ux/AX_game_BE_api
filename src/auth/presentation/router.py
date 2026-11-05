# 가입, 로그인과 로그아웃 요청을 서비스에 전달하고 HTTP 응답으로 변환한다.
from fastapi import APIRouter, Depends, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timezone

from auth.application.service import AuthService
from auth.presentation.dependencies import get_auth_service, get_bearer_token
from auth.presentation.schemas import RegisterUserRequest, RegisterUserResponse, TokenResponse

# 공통 /v1 접두사는 main.py의 앱 등록 시 적용한다.
router = APIRouter(prefix="/auth", tags=["auth"])

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterUserResponse,
)
async def register_user(
    request: RegisterUserRequest, service: AuthService = Depends(get_auth_service)
) -> RegisterUserResponse:
    result = await service.register_user(
        login_id=request.login_id,
        display_name=request.display_name,
        password=request.password,
    )

    # 시간대가 누락된 가입 시각은 내부 데이터 오류로 처리한다.
    if result.created_at.utcoffset() is None:
        raise RuntimeError("회원 가입 시각에 시간대 정보가 없습니다.")
    return RegisterUserResponse(
        id=str(result.id),
        login_id=result.login_id,
        created_at=result.created_at.astimezone(timezone.utc),
    )


@router.post("/token", response_model=TokenResponse)
async def login(
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    # OAuth2 폼의 username은 프로젝트의 login_id에 대응한다.
    result = await service.login(login_id=form.username, password=form.password)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return TokenResponse(access_token=result.access_token, expires_in=result.expires_in)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    token: str = Depends(get_bearer_token),
    service: AuthService = Depends(get_auth_service),
) -> Response:
    # 현재 토큰만 폐기한다. 다른 기기의 토큰은 그대로 유지한다.
    await service.logout(token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

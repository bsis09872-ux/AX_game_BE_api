# 회원가입 요청을 서비스에 전달하고 외부 응답의 ID와 가입 시각을 변환한다.
from fastapi import APIRouter, Depends, status
from datetime import timezone

from auth.application.service import AuthService
from auth.presentation.dependencies import get_auth_service
from auth.presentation.schemas import RegisterUserRequest, RegisterUserResponse

# 공통 /v1 접두사는 main.py의 앱 등록 시 적용한다.
# TODO: 가입 서비스의 지갑 생성과 commit, 실패 시 rollback을 검증한 뒤 앱에 등록한다.
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

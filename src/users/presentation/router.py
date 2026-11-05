# 토큰의 회원 ID로 본인 정보를 조회한다. 클라이언트가 조회 대상을 지정하지 않는다.
from fastapi import APIRouter, Depends, Response

from auth.application.contracts import TokenClaims
from auth.presentation.dependencies import get_current_token
from auth.domain.exceptions import InvalidTokenError
from users.application.service import UserService
from users.presentation.dependencies import get_user_service
from users.presentation.schemas import UserMeResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    response: Response,
    claims: TokenClaims = Depends(get_current_token),
    service: UserService = Depends(get_user_service),
) -> UserMeResponse:
    user = await service.get_user(claims.user_id)
    if not user.is_active():
        raise InvalidTokenError()
    response.headers["Cache-Control"] = "no-store"
    return UserMeResponse.from_user(user)

"""낚시터 화면 라우터 (GET /play, Jinja2)

- 로그인 확인(쿠키의 회원 번호)은 main에서 넘겨 받는다 (auth의 쿠키 구조를 모른다).
  로그인이 안 됐으면 auth의 핸들러가 /login으로 이동시킨다
- 화면의 동작은 static/game/play.js의 initPlayPage가 맡는다 (pages.js에 page_key "play"로 등록)
- 낚시 결과와 골드는 화면이 팀 API(POST /v1/fishing-results, GET /v1/wallets/me)를 직접 부른다
- 개인 화면이라 브라우저에 저장하지 않게 한다 (Cache-Control: no-store)
"""

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

# 맵 이름: static/maps/{map}.tmj. 영문·숫자·_·- 32자까지 (경로 조작 방지). 틀리면 422
MAP_PATTERN = r"^[\w-]{1,32}$"
DEFAULT_MAP = "world"


def create_game_web_router(current_user_id: Callable[..., Awaitable[int]]) -> APIRouter:
    """낚시터 화면 라우터를 만든다.

    current_user_id: 쿠키를 확인해 회원 번호를 돌려주는 의존성 (auth의 get_current_web_user_id)
    """
    router = APIRouter(tags=["game"])

    @router.get("/play", response_class=HTMLResponse, include_in_schema=False)
    async def play_page(
        request: Request,
        map: str = Query(DEFAULT_MAP, pattern=MAP_PATTERN),
        user_id: int = Depends(current_user_id),
    ) -> HTMLResponse:
        response = request.app.state.templates.TemplateResponse(
            request=request,
            name="game/play.html",
            context={"map_name": map},
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    return router

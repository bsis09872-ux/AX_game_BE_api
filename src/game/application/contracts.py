"""낚시터가 다른 도메인에 바라는 기능 (계약)

- 구현은 infrastructure/adapters에 있고, 조립은 wiring이 한다
- 다른 도메인의 모델·테이블을 직접 읽지 않고, 그 도메인이 공개한 서비스만 호출한다
- 낚시 결과와 골드는 화면이 팀 API(POST /v1/fishing-results, GET /v1/wallets/me)를 직접 부른다. 그래서 여기에 계약이 없다
"""

from typing import Protocol

from game.application.dto import PlayerIdentity


class PlayerDirectory(Protocol):
    # auth로 토큰을 확인하고 users에서 닉네임·활성 여부를 가져온다.
    # 토큰이 틀렸거나 만료됐거나 비활성 회원이면 None
    async def authenticate(self, access_token: str) -> PlayerIdentity | None: ...

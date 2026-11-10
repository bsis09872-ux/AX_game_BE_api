"""낚시터 라우터의 의존성 주입(Depends) 함수

- 허브와 접속자 확인기를 밖(wiring)에서 만들어 넘긴다. 업무 규칙을 두지 않는다
- 테스트에서는 app.dependency_overrides로 가짜를 넣는다
"""

from game.application.contracts import PlayerDirectory
from game.application.hub import WorldHub
from game.wiring import get_player_directory, get_world_hub


def get_hub() -> WorldHub:
    return get_world_hub()


def get_directory() -> PlayerDirectory:
    return get_player_directory()

"""낚시터 응용 계층이 주고받는 값"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerIdentity:
    # 쿠키의 access token으로 확인한 접속자. ID는 내부에서 int, 메시지로 나갈 때 문자열로 바꾼다
    user_id: int
    nickname: str

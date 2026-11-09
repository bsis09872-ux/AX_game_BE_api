"""지갑이 다른 도메인에 요청하는 기능의 계약 (내가 필요한 것)

- 계약은 필요한 기능의 모양(Protocol)만 적는다. 구현은 infrastructure 어댑터가 하고 wiring이 연결한다.
- 서비스는 이 모양만 알고, 누가 어떻게 구현했는지(users 서비스, listings 테이블 등)는 모른다.
- 다른 도메인의 모델이나 infrastructure를 import하지 않는다.
- 어댑터는 이 파일을 import하지 않고 메서드 모양만 맞춘다(Protocol의 구조적 타이핑).
  그래야 infrastructure → application 방향의 import가 생기지 않는다.
- 테스트에서는 같은 모양의 가짜를 끼운다.

RoleCheck:        요청한 회원이 관리자인지 (users 도메인)
HeldAmountReader: 회원의 입찰로 묶인 금액 합계 (auction 도메인)
"""
from typing import Protocol


# users에게 필요한 것: 관리자 충전 권한 확인
class RoleCheck(Protocol):

    # user_id는 presentation이 인증으로 확인해 넘긴 요청자 ID다.
    # 반환: 관리자면 True. 회원이 없으면 구현체가 NotFoundError 계열 예외를 올린다.
    async def is_admin(self, user_id: int) -> bool:
        ...


# auction에게 필요한 것: 예약(hold) 금액
class HeldAmountReader(Protocol):

    # 내가 현재 최고 입찰자(current_bidder_id)인 BIDDING 매물들의 입찰액 합계. 없으면 0.
    # 마감이 지나도 정산 전이면 BIDDING이라 포함된다.
    # 입찰 확인(WALL-07)에서는 지갑 잠금 뒤에 불러야 같은 회원의 동시 입찰이 반영된다.
    async def held_amount(self, user_id: int) -> int:
        ...

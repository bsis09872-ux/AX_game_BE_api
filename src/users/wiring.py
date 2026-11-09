# 회원 서비스와 SQLAlchemy 저장소를 연결한다.
from sqlalchemy.ext.asyncio import AsyncSession

from users.application.service import UserService
from users.infrastructure.repositories import SqlAlchemyUserRepository


def build_user_service(session: AsyncSession) -> UserService:
    # TODO(경매 연동): application.contracts.AuctionMemberGateway를 경매 어댑터에 연결한다.
    # 입찰 허용 검사는 effective_auction_blocked_until, 자동 제한 정책 계산은
    # auction_blocked_until을 사용한다. 매물 -> 아이템 -> 회원 -> 지갑 잠금 순서와
    # 동일 세션을 유지한다. 현재 이 wiring만으로 실제 입찰 차단이 연결된 것은 아니다.
    # 요청의 세션을 공유하며, 세션 종료는 호출자가 담당한다.
    repository = SqlAlchemyUserRepository(session=session)
    return UserService(repository=repository)

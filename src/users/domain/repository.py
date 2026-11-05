# 회원 조회 계약. DB 구현과 관계없이 도메인 User 또는 None을 반환한다.
from abc import ABC, abstractmethod

from users.domain.user import User


# 조회와 생성 계약을 모두 구현한 자식 클래스만 인스턴스를 생성할 수 있다.
class UserRepository(ABC):
    # ID로 회원을 조회한다. 회원이 없을 때의 업무 처리는 application에서 결정한다.
    @abstractmethod
    async def find_by_id(self, user_id: int) -> User | None:
        pass

    # 로그인 ID가 정확히 일치하는 회원을 조회한다. 입력을 변환하거나 부분 검색하지 않는다.
    @abstractmethod
    async def find_by_login_id(self, login_id: str) -> User | None:
        pass

    # ID가 없는 신규 회원을 저장하고, 생성된 ID를 가진 User를 반환한다.
    # 실패는 예외로 전달하며 전체 작업의 commit은 이 계약에 포함하지 않는다.
    @abstractmethod
    async def create(self, user: User) -> User:
        pass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from users.domain.repository import UserRepository
from users.domain.user import User
from users.infrastructure.models import UserModel
from users.domain.exceptions import InvalidUserError


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    def _to_domain(self, model: UserModel) -> User:
        return User(
            model.login_id,
            model.password_hash,
            display_name=model.display_name,
            user_id=model.id,
            auction_purchase_count=model.auction_purchase_count,
            auction_blocked_until=model.auction_blocked_until,
            created_at=model.created_at,
            updated_at=model.updated_at,
            role=model.role,
            deleted_at=model.deleted_at,
        )

    async def find_by_id(self, user_id: int) -> User | None:
        user_model = await self.session.get(UserModel, user_id)

        if user_model is None:
            return None

        return self._to_domain(user_model)

    async def find_by_login_id(self, login_id: str) -> User | None:
        statement = select(UserModel).where(UserModel.login_id == login_id)

        result = await self.session.execute(statement)

        user_model = result.scalar_one_or_none()

        if user_model is None:
            return None

        return self._to_domain(user_model)

    async def create(self, user: User) -> User:
        if user.id is not None:
            raise InvalidUserError("이미 저장된 회원은 새로 생성할 수 없습니다.")

        user_model = UserModel(
            login_id=user.login_id,
            password_hash=user.password_hash,
            display_name=user.display_name,
            role=user.role,
            auction_purchase_count=user.auction_purchase_count,
            auction_blocked_until=user.auction_blocked_until,
            deleted_at=user.deleted_at,
        )
        self.session.add(user_model)
        await self.session.flush()
        return self._to_domain(user_model)

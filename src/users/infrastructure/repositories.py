# SQLAlchemy로 회원을 조회하거나 저장하고 결과를 도메인 User로 변환한다.
from sqlalchemy import select, func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from users.domain.repository import UserRepository
from users.domain.user import User
from users.infrastructure.models import UserModel
from users.domain.exceptions import InvalidUserError, LoginIdAlreadyExistsError, UserNotFoundError


class SqlAlchemyUserRepository(UserRepository):
    # 주입받은 세션을 공유한다. 세션 생성과 트랜잭션 확정은 호출 측에서 담당한다.
    def __init__(self, session: AsyncSession):
        self.session = session

    async def lock_administration(self) -> None:
        # 서로를 동시에 강등하는 관리자 요청을 한 트랜잭션씩 처리한다.
        await self.session.execute(text('SELECT pg_advisory_xact_lock(731401, 1)'))

    async def count_available_admins(self) -> int:
        return await self.session.scalar(select(func.count()).select_from(UserModel).where(
            UserModel.role == 'ADMIN', UserModel.deleted_at.is_(None)))

    async def save_admin_settings(self, user: User) -> None:
        row = await self.session.get(UserModel, user.id)
        if row is None:
            raise UserNotFoundError()
        row.role = user.role
        await self.session.flush()

    async def list_members(self, query: str, role: str | None, page: int, size: int) -> tuple[list[User], int]:
        conditions = []
        if query:
            conditions.append(or_(UserModel.login_id.icontains(query, autoescape=True),
                                  UserModel.display_name.icontains(query, autoescape=True)))
        if role:
            conditions.append(UserModel.role == role)
        total = await self.session.scalar(select(func.count()).select_from(UserModel).where(*conditions))
        rows = (await self.session.scalars(select(UserModel).where(*conditions)
                .order_by(UserModel.id.desc()).offset((page - 1) * size).limit(size))).all()
        return [self._to_domain(row) for row in rows], total

    async def find_for_update_many(self, user_ids: list[int]) -> dict[int, User]:
        if not user_ids:
            return {}
        statement = (
            select(UserModel).where(UserModel.id.in_(sorted(set(user_ids))))
            .order_by(UserModel.id).with_for_update()
            .execution_options(populate_existing=True)
        )
        rows = (await self.session.scalars(statement)).all()
        return {row.id: self._to_domain(row) for row in rows}

    async def save_auction_limit(self, user: User) -> None:
        row = await self.session.get(UserModel, user.id)
        if row is None:
            raise UserNotFoundError()
        row.auction_purchase_count = user.auction_purchase_count
        row.auction_blocked_until = user.auction_blocked_until
        await self.session.flush()

    # DB에서 읽은 ID, 역할, 탈퇴 상태를 보존한다. 이 변환 자체에는 DB 통신이 없다.
    # 가입 시각과 수정 시각도 User에 전달한다.
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

    # 탈퇴 회원도 반환해 인증 계층에서 활성 상태를 판단할 수 있게 한다.
    # 조회 결과가 없으면 변환 전에 None을 반환한다.
    async def find_by_id(self, user_id: int) -> User | None:
        user_model = await self.session.get(UserModel, user_id)

        if user_model is None:
            return None

        return self._to_domain(user_model)

    # 조회문(statement), 실행 결과(result), ORM 객체(user_model)를 구분한다.
    # 정확히 일치하는 회원을 찾고, 여러 행이 나오거나 DB가 실패하면 오류를 전파한다.
    async def find_by_login_id(self, login_id: str) -> User | None:
        statement = select(UserModel).where(UserModel.login_id == login_id)

        result = await self.session.execute(statement)

        user_model = result.scalar_one_or_none()

        if user_model is None:
            return None

        return self._to_domain(user_model)

    # 신규 회원만 등록하며 기존 회원의 갱신은 처리하지 않는다.
    async def create(self, user: User) -> User:
        # 이미 ID가 있는 객체의 중복 생성을 DB 작업 전에 막는다.
        if user.id is not None:
            raise InvalidUserError("이미 저장된 회원은 새로 생성할 수 없습니다.")

        # 해싱된 비밀번호와 회원 상태를 옮기고 ID와 가입 시각은 DB에 맡긴다.
        user_model = UserModel(
            login_id=user.login_id,
            password_hash=user.password_hash,
            display_name=user.display_name,
            role=user.role,
            auction_purchase_count=user.auction_purchase_count,
            auction_blocked_until=user.auction_blocked_until,
            deleted_at=user.deleted_at,
        )
        # flush로 INSERT를 보내 생성된 ID를 받는다. 최종 commit은 서비스 흐름이 담당한다.
        self.session.add(user_model)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            db_error = exc.orig.__cause__
            sqlstate = getattr(db_error, "sqlstate", None)
            table_name = getattr(db_error, "table_name", None)
            constraint_name = getattr(db_error, "constraint_name", None)

            # 동시 가입은 사전 조회를 함께 통과할 수 있어 로그인 ID 제약 위반만 중복 예외로 바꾼다.
            if (
                sqlstate == "23505"
                and table_name == "users"
                and constraint_name == "users_login_id_key"
            ):
                raise LoginIdAlreadyExistsError() from exc
            raise

        # 입력 객체는 그대로 두고 ID가 채워진 새 User를 반환한다.
        return self._to_domain(user_model)

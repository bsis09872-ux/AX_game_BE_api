# users 테이블의 컬럼, 기본값과 제약 조건을 SQLAlchemy 모델로 정의한다.
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class UserModel(Base):
    __tablename__ = "users"
    # DB에도 역할의 허용 값을 제한한다. 관리자 지정 권한 자체는 인증/가입 흐름이 검사한다.
    __table_args__ = (
        CheckConstraint(
            "role IN ('USER', 'ADMIN')",
            name="ck_users_role",
        ),
    )
    # PostgreSQL이 새 회원 ID를 생성하고, 로그인 ID 중복은 DB 유일 제약으로 막는다.
    id: Mapped[int] = mapped_column(BigInteger(), primary_key=True)

    login_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    # 비밀번호 원문 대신 해시 결과만 저장한다.
    password_hash: Mapped[str] = mapped_column(String(), nullable=False)

    display_name: Mapped[str] = mapped_column(String(), nullable=False)

    # SQLAlchemy와 DB INSERT의 기본 역할은 USER다. 객체 생성 직후의 값과는 구분한다.
    role: Mapped[str] = mapped_column(
        String(5), nullable=False, default="USER", server_default="USER"
    )

    auction_purchase_count: Mapped[int] = mapped_column(default=0, server_default="0")
    auction_blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manual_auction_blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    login_suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 탈퇴하지 않은 회원은 NULL이며, 시간대 정보를 포함하는 시각으로 저장한다.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # 가입 시각은 INSERT 시 DB가 채운다.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

"""SQLAlchemy 모델: item_definitions, inventory_items, item_events 테이블

- 테이블 이름은 복수 snake_case, 컬럼은 snake_case, 기본키는 id다
- 잘못된 값이 DB에 들어가지 못하게 제약(CHECK, FK, UNIQUE)을 둔다
  category, rarity, status, origin의 허용값, start_price 0 초과, weight 0 이상, code 고유
- item_events는 쌓기만 한다. (item_id, created_at) 인덱스를 두고 listing_id, trade_id에는 FK를 걸지 않는다
- 시각 컬럼은 시간대가 있는 UTC 값이다
- 도메인 객체와 이 모델 사이의 변환은 repositories.py가 맡는다
- owner_id, from_owner_id, to_owner_id, actor_id는 users.id를 가리키는 FK다. 사용자가 남아 있는 동안은 지울 수 없다 (회원 탈퇴는 deleted_at으로 소프트 삭제)
- users 테이블 등록은 앱을 조립하는 main.py가 한다. 이 파일은 다른 도메인의 모델을 import하지 않고 FK 문자열("users.id")만 쓴다
- inventory_items.updated_at은 ORM이 행을 수정할 때마다 DB 시각으로 바뀐다 (onupdate)
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func, # 모듈이 아닌 객체 (SQL 함수 이름을 붙이면 그 SQL 함수 호출을 만들어 준다)
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

class ItemDefinitionModel(Base):
    # 테이블 이름 지정
    __tablename__ = 'item_definitions'
    # 테이블 컬럼 생성
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(20))
    rarity: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text, server_default='')
    icon: Mapped[str] = mapped_column(String(50), server_default='default')
    weight: Mapped[int] = mapped_column(Integer, server_default=text('10'))
    fishable: Mapped[bool] = mapped_column(Boolean, server_default=text('true'))
    start_price: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    # 테이블 제약 조건
    # 튜플 형태로 제약 조건이나 인덱스를 나열한다
    # 스키마나 SQL 엔진 같은 옵션은 딕셔너리 형태로 튜플의 가장 마지막 요소에 넣어야 한다
    # 왜 컬럼 생성할 때 안 넣나? → 여러 컬럼을 묶거나 형식을 지정해야 할 때는 여기에 적는다
    __table_args__ = (
        UniqueConstraint(
            'code', name='uq_item_definitions_code'
        ),
        CheckConstraint(
            "code ~ '^[a-z][a-z0-9_]{2,49}$'", name='ck_item_definitions_code_format'
        ),
        CheckConstraint(
            "category IN ('FISH', 'GEM', 'MISC')", name='ck_item_definitions_category'
        ),
        CheckConstraint(
            "rarity IN ('COMMON', 'UNCOMMON', 'RARE', 'EPIC', 'LEGENDARY')", name='ck_item_definitions_rarity',
        ),
        CheckConstraint(
            'weight >= 0', name='ck_item_definitions_weight'
        ),
        CheckConstraint(
            'start_price > 0', name='ck_item_definitions_start_price'
        ),
    )

class InventoryItemModel(Base):
    # 테이블 이름 지정
    __tablename__ = 'inventory_items'
    # 테이블 컬럼 생성
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    item_definition_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('item_definitions.id', ondelete='RESTRICT'))
    # users.id를 가리키는 외래키: 없는 사용자 번호는 저장되지 않는다
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='RESTRICT'))
    status: Mapped[str] = mapped_column(String(10), server_default='OWNED')
    origin: Mapped[str] = mapped_column(String(20))
    acquired_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    resale_available_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    # 테이블 제약 조건
    __table_args__ = (
        CheckConstraint(
            "status IN ('OWNED', 'LISTED')", name='ck_inventory_items_status'
        ),
        CheckConstraint(
            "origin IN ('SEED', 'ADMIN_GRANT', 'REWARD', 'TRADE')", name='ck_inventory_items_origin'
        ),
        Index(
            'ix_inventory_items_owner_status', 'owner_id', 'status', text('acquired_at DESC')
        ), # 최신 획득 순서대로 정렬
        Index('ix_inventory_items_definition', 'item_definition_id')
    )

class ItemEventModel(Base):
    # 테이블 이름 지정
    __tablename__ = 'item_events'
    # 테이블 컬럼 생성
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    item_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('inventory_items.id', ondelete='RESTRICT'))
    event_type: Mapped[str] = mapped_column(String(20))
    from_owner_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='RESTRICT'))
    to_owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='RESTRICT'))
    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('users.id', ondelete='RESTRICT'))
    listing_id: Mapped[int | None] = mapped_column(BigInteger)
    trade_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    # 테이블 제약 조건
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('GRANTED', 'LISTED', 'UNLISTED', 'TRANSFERRED')", name='ck_item_events_type'
        ),
        CheckConstraint(
            "(event_type = 'GRANTED' AND from_owner_id IS NULL"
            " AND to_owner_id IS NOT NULL)" # GRANTED면 from이 비어야 한다
            " OR (event_type IN ('LISTED', 'UNLISTED')"
            " AND from_owner_id IS NOT NULL AND from_owner_id = to_owner_id)" # LISTED 또는 UNLISTED면 from과 to가 같다
            " OR (event_type = 'TRANSFERRED' AND from_owner_id IS NOT NULL"
            " AND to_owner_id IS NOT NULL AND from_owner_id <> to_owner_id)", # TRANSFERRED면 from과 to가 다르다
            name='ck_item_events_owners'
        ),
        Index(
            'ix_item_events_item_created', 'item_id', 'created_at'
        )
    )
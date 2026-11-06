"""다른 도메인 테이블의 조회·기록용 가벼운 참조 (ERD Ver_4.0)

sqlalchemy.table()/column()은 Base.metadata에 등록되지 않는다.
그래서 create_all이 이 정의로 테이블을 만들거나 다른 도메인 ORM 모델과 부딪히지 않는다.
필요한 컬럼만 적는다.

TODO: auction(listings·trades)·users 쪽에 "조회 기능"이 합의되면 그 기능으로 바꾸고 이 파일을 줄인다.
"""
from sqlalchemy import BigInteger, DateTime, String, column, table

users = table(
    "users",
    column("id", BigInteger),
    column("display_name", String),
)

item_definitions = table(
    "item_definitions",
    column("id", BigInteger),
    column("name", String),
)

listings = table(
    "listings",
    column("id", BigInteger),
    column("item_definition_id", BigInteger),
    column("seller_id", BigInteger),
    column("current_bidder_id", BigInteger),
    column("current_bid_amount", BigInteger),
    column("status", String),
)

trades = table(
    "trades",
    column("id", BigInteger),
    column("listing_id", BigInteger),
    column("buyer_id", BigInteger),
    column("item_name_snapshot", String),
    column("seller_name_snapshot", String),
    column("buyer_name_snapshot", String),
    column("price_snapshot", BigInteger),
    column("completed_at", DateTime(timezone=True)),
)

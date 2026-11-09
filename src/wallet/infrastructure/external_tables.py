"""다른 도메인 테이블의 조회용 가벼운 참조

sqlalchemy.table()/column()은 Base.metadata에 등록되지 않는다.
그래서 create_all이 이 정의로 테이블을 만들거나 다른 도메인 ORM 모델과 부딪히지 않는다.
지금 실제로 쓰는 것(held_amount_reader.py의 listings)만, 필요한 컬럼만 적는다.

TODO: auction이 예약금 조회 기능을 공개하면 그 기능으로 바꾸고 이 파일을 지운다.
"""
from sqlalchemy import BigInteger, String, column, table

listings = table(
    "listings",
    column("current_bidder_id", BigInteger),
    column("current_bid_amount", BigInteger),
    column("status", String),
)

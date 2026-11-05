from sqlalchemy.orm import DeclarativeBase


# 각 도메인의 ORM 모델이 이 클래스를 상속하면 테이블 정의가 Base.metadata에 모인다.
class Base(DeclarativeBase):
    pass

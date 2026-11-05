# __tablename__ = "listings"
#
# [PK]
#   id: BigInteger, 자동 증가
#
# [FK] — ondelete는 전부 RESTRICT 추천
#   inventory_item_id  → inventory_items.id  (필수, index)
#   item_definition_id → item_definitions.id (필수, index)  ※ 대기열 그룹 기준
#   seller_id          → users.id            (필수, index)
#   current_bidder_id  → users.id            (NULL 허용, index)
#     └ 이유: 경매 기록은 사라지면 안 됨. users는 소프트 삭제(deleted_at)이니 CASCADE 불필요
#
# [금액] — BigInteger
#   start_price          (필수)
#   current_bid_amount   (NULL 허용: 입찰 전에는 없음)
#
# [상태]
#   status: String(20), 기본값 QUEUED, index
#     └ DB에는 문자열로 저장, 파이썬에서는 domain/enums.py의 Enum 값을 사용
#
# [시간] — DateTime(timezone=True), 기본값은 "함수 자체"
#   created_at (필수, 대기열 등록 시각)
#   started_at / ends_at / closed_at (전부 NULL 허용: 상태가 진행되며 채워짐)
#   updated_at (onupdate)
#
# [제약] __table_args__ 에 CheckConstraint
#   - start_price > 0
#   - current_bid_amount IS NULL 이거나 >= start_price
#   - status는 4개 값 중 하나
#   - current_bidder_id와 current_bid_amount는 "둘 다 NULL이거나 둘 다 값 있음"
#
# [복합 인덱스] — 자주 쓰는 조회 패턴에 맞춰
#   (item_definition_id, status, created_at)  → "이 아이템 종류의 다음 대기 매물"
#   (status, ends_at)                          → "마감 시간이 지난 진행 중 매물" 찾기
#
# [relationship]
#   trade: 1:0..1, uselist=False, lazy="joined", back_populates="listing"
#   다른 도메인 모델(User, InventoryItem)과는 relationship 걸지 않기 → 아래 4번 참고


#---------------------------

# __tablename__ = "trades"
#
#   id: BigInteger, 자동 증가
#   listing_id → listings.id  (필수, unique=True  ← "매물당 거래 1건"을 DB가 보장)
#   buyer_id   → users.id     (필수, index, RESTRICT)
#
#   [스냅샷] 체결 시점 값을 "복사"해 두는 컬럼 → 원본이 바뀌어도 거래 기록은 그대로
#     item_name_snapshot   String(100)
#     seller_name_snapshot String(50)
#     buyer_name_snapshot  String(50)
#     price_snapshot       BigInteger, CheckConstraint(> 0)
#
#   completed_at (필수)
#   ※ updated_at 없음 → 거래 기록은 수정하지 않는 "불변 데이터"
#
#   listing: relationship, back_populates="trade"

#-------
# ✅ FK는 문자열로만 참조: ForeignKey("users.id")
#    → users 모델 클래스를 import하지 않아도 됨
#
# ❌ listing 모델에서 User, InventoryItem 클래스를 import해서 relationship 걸기
#    → 도메인끼리 얽히고 순환 import 위험
#
# ⚠️ 대신 create_all 전에 "참조 대상 테이블"이 metadata에 등록돼 있어야 함
#    → init_models()에 users, inventory, wallet, listing 모델을 "전부" import
#    → 빠지면: NoReferencedTableError
#
# 다른 도메인 정보가 필요하면? → Service에서 그 도메인의 Repository(또는 Service)를 받아서 조회
#   예: 판매자 이름 → users 쪽에 "id로 이름 조회" 기능 요청
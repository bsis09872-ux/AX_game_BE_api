"""요청·응답 모델(Pydantic)

- 요청 모델 이름은 ...Request, 응답 모델 이름은 ...Response로 쓴다
- 요청 모델은 extra="forbid"로 정해진 필드 외의 값을 거절한다 (이름, 등급, 소유자를 클라이언트가 보내지 못한다)
- 아이템 요청에서 클라이언트가 보내는 것은 item_id뿐이다
- 밖으로 나가는 ID는 문자열이고 안쪽 ID는 int다 (변환은 이 경계에서만 한다)
- 시각은 ISO 8601 UTC로 내보낸다
- 응답에 다른 사용자의 정보나 내부 값을 싣지 않는다
"""

from datetime import datetime, timezone
from typing import Generic, TypeVar
from pydantic import BaseModel

from inventory.application.dto import DefinitionInfo, ItemInfo

# 어떤 항목이든 담을 수 있는 타입 자리표시자
T = TypeVar('T')

# 시간 맞추기
def _utc(value: datetime | None) -> datetime | None:
    return None if value is None else value.astimezone(timezone.utc)


# 아이템 카탈로그 요약: 여기에 적은 필드만 밖으로 나간다
class DefinitionSummaryResponse(BaseModel):
    id: str
    code: str
    name: str
    category: str
    rarity: str
    icon: str
    start_price: int

    # 서비스가 던진 DTO 응답 모델로 변환
    @classmethod
    def from_info(cls, info: DefinitionInfo) -> 'DefinitionSummaryResponse':
        return cls(
            id=str(info.id), code=info.code, name=info.name, category=info.category, rarity=info.rarity, icon=info.icon, start_price=info.start_price
        )


# 아이템 카탈로그 전체: 요약 + 설명 (상세 조회와 카탈로그 목록에서 사용)
class ItemDefinitionResponse(DefinitionSummaryResponse):
    description: str

    # 서비스가 던진 DTO 응답 모델로 변환
    @classmethod
    def from_info(cls, info: DefinitionInfo) -> 'ItemDefinitionResponse':
        return cls(
            id=str(info.id), code=info.code, name=info.name, category=info.category, rarity=info.rarity, icon=info.icon, start_price=info.start_price, description=info.description
        )


# 내 아이템 목록
class InventoryItemResponse(BaseModel):
    id: str
    definition: DefinitionSummaryResponse
    status: str
    origin: str
    acquired_at: datetime
    resale_available_at: datetime | None

    # 서비스가 던진 DTO 응답 모델로 변환
    @classmethod
    def from_info(cls, info: ItemInfo) -> 'InventoryItemResponse':
        return cls(
            id=str(info.id), definition=DefinitionSummaryResponse.from_info(info.definition), status=info.status, origin=info.origin, acquired_at=_utc(info.acquired_at), resale_available_at=_utc(info.resale_available_at)
        )


# 내 아이템 상세: 내 아이템 목록 + 카탈로그 전체
class InventoryItemDetailResponse(BaseModel):
    id: str
    definition: ItemDefinitionResponse
    status: str
    origin: str
    acquired_at: datetime
    resale_available_at: datetime | None

    # 서비스가 던진 DTO 응답 모델로 변환
    @classmethod
    def from_info(cls, info: ItemInfo) -> 'InventoryItemDetailResponse':
        return cls(
            id=str(info.id), definition=ItemDefinitionResponse.from_info(info.definition), status=info.status, origin=info.origin, acquired_at=_utc(info.acquired_at), resale_available_at=_utc(info.resale_available_at)
        )


# 화면에 뿌려질 목록의 응답 틀 (페이지네이션)
class PageResponse(BaseModel, Generic[T]):
    items: list[T]
    page: int
    size: int
    total: int
"""개별 아이템(InventoryItem): 특정 계정이 가진 아이템 한 개와 상태 전이

- 소유자는 항상 정확히 1명이고, 존재하는 아이템 카탈로그 하나를 가리킨다
- 상태는 OWNED(보관)와 LISTED(경매 판매 예약) 두 가지다
- OWNED -> LISTED: 소유자 본인만, 상태가 OWNED이고 resale_available_at이 없거나 지난 뒤에만
- LISTED -> OWNED(판매자 그대로): 소유자 본인만, acquired_at은 바꾸지 않는다
- LISTED -> OWNED(낙찰자): 새 소유자는 현재 소유자와 달라야 하고 acquired_at, origin(TRADE), resale_available_at을 갱신한다
- 소유자가 바뀌는 경로는 transfer_to 하나뿐이다. grant는 아이템을 새로 만드는 것이다
- 상태나 소유자가 바뀔 때마다 ItemEvent 1건을 만들어 들고 있고, 저장은 레포지토리가 한다
    - 단, 요청 실패 시 재시도 또는 실패 상황을 이어서 처리하는 경우 이력 누락이 발생할 수 있다
    - 따라서 이력 누락을 방지하기 위해 요청마다 DB를 새로 읽고 객체를 절대 보관하지 않는다 
    - 또한 실패한 객체로 요청을 재시도하지 않는다 (관련 코드는 어디에도 생성하지 않는다)
- 시각은 now를 인자로 받는다 (시계를 직접 읽지 않는다. 시간대가 있는 UTC 값이다)
- 재판매는 resale_available_at 정각부터 등록할 수 있다 (now가 그 시각 이상이면 허용)
- 검사는 입력 형식, 소유자, 상태, 재판매 시각 순서로 하고, 모두 통과한 뒤에만 값을 바꾼다 (실패하면 상태와 이력이 그대로다)
- 규칙 위반은 도메인이 직접 예외를 던진다 (서비스나 라우터의 if-else로 판정하지 않는다)
- 순수 파이썬만 쓴다 (FastAPI, Pydantic, SQLAlchemy, logging을 import하지 않는다)
"""

from datetime import datetime, timedelta
from inventory.domain.enums import ItemEventType, ItemOrigin, ItemStatus
from inventory.domain.exceptions import (
    InvalidStateError,
    ItemRuleViolationError,
    NotOwnerError,
    ResaleNotAvailableError,
)
from inventory.domain.item_definition import ItemDefinition
from inventory.domain.item_event import ItemEvent

# 재판매 제한 시간
DEFAULT_RESALE_DELAY = timedelta(minutes=30)

# 아이템 획득 출처 제한 (거래는 획득이 아닌 소유권 이전으로 본다)
_GRANT_ORIGINS = {ItemOrigin.SEED, ItemOrigin.ADMIN_GRANT, ItemOrigin.REWARD}

def _check_id(field: str, value) -> int:
    # bool은 int의 자식이고 True가 1로 통과하므로 따로 체크
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ItemRuleViolationError(f'{field}는 1 이상의 정수여야 합니다.')
    return value

def _check_now(now) -> datetime:
    # 시간대가 없는 시각과 있는 시각을 비교하면 TypeError 발생
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ItemRuleViolationError('now는 시간대가 있는 시각이어야 합니다.')
    return now

class InventoryItem:
    # 우선 값을 그대로 저장 + 새로 만들 때는 grant를 사용한다
    # 아래 생성자는 레포지토리가 DB 행에서 객체를 만들 때 쓴다 
    def __init__(
        self,
        definition: ItemDefinition,
        owner_id: int,
        status: ItemStatus,
        origin: ItemOrigin,
        acquired_at: datetime,
        resale_available_at: datetime | None=None,
        id: int | None=None,
    ) -> None:
        self.id = id
        self.definition = definition
        self.owner_id = owner_id
        self.status = status
        self.origin = origin
        self.acquired_at = acquired_at
        self.resale_available_at = resale_available_at
        self._events: list[ItemEvent] = [] # 저장 내역 없는 이력

    @classmethod
    def grant(
        cls,
        definition: ItemDefinition,
        owner_id: int,
        origin: ItemOrigin,
        now:datetime,
        actor_id: int | None=None,                
    ) -> 'InventoryItem':
        
        if not isinstance(definition, ItemDefinition):
            raise ItemRuleViolationError('아이템 카탈로그(definition)에 해당하는 내용이어야 합니다.')
        _check_id('owner_id', owner_id)
        
        if not isinstance(origin, ItemOrigin) or origin not in _GRANT_ORIGINS:
            raise ItemRuleViolationError('아이템 획득(origin)은 SEED, ADMIN_GRANT, REWARD 출처만 가능합니다.')
        _check_now(now)

        # 아이템 획득 → 아이템 이력 행 추가
        item = cls(definition, owner_id, ItemStatus.OWNED, origin, now)
        item._events.append(
            ItemEvent(ItemEventType.GRANTED, None, owner_id, now, actor_id=actor_id)
        )
        return item
    
    # 매물 등록과 취소는 모두 owner(소유자)를 actor(요청자)로 한다
    # actor는 user 아니면 system(Null)
    def _require_owner(self, by_owner_id: int) -> None:
        if by_owner_id != self.owner_id:
            raise NotOwnerError()

    # 매물 등록 관련
    def reserve_for_listing(
            self, by_owner_id: int, now: datetime, listing_id: int | None=None
    ) -> None:
        _check_now(now)
        self._require_owner(by_owner_id)

        # 판매하려는 아이템의 진소유자인지 확인
        if self.status != ItemStatus.OWNED:
            raise InvalidStateError()

        # 판매하려는 아이템이 재판매 제한에 걸렸는지 확인
        if self.resale_available_at is not None and now < self.resale_available_at:
            raise ResaleNotAvailableError(
                f'{self.resale_available_at.isoformat()} 이후에 다시 등록할 수 있습니다.'
            )

        # 판매하려는 아이템이 매물 등록 조건을 충족하면 잠근다
        self.status = ItemStatus.LISTED
        # 그리고 매물 등록에 대한 아이템 이력을 추가한다
        self._events.append(
            ItemEvent(
                # 아이템을 잠금 상태로 만들고
                ItemEventType.LISTED,
                # 아직 유저 간 전이가 없으므로 모두 owner
                self.owner_id,
                self.owner_id,
                now,
                actor_id=by_owner_id,
                listing_id=listing_id
            )
        )

    # 매물이 원소유자로 되돌아올 때 (유찰, 거래 취소 등)
    def release_from_listing(
            self, by_owner_id: int, now: datetime, listing_id: int | None=None
    ) -> None:
        _check_now(now)
        self._require_owner(by_owner_id)

        # 잠겨있는 상태인지 확인 (매물 등록된 상태였어야 하기 때문)
        if self.status != ItemStatus.LISTED:
            raise InvalidStateError()

        # 아이템을 소유 상태로 변경하고 (소유권 이전이 없으므로 acquired_at 업데이트 없음)
        self.status = ItemStatus.OWNED
        # 잠금 상태였던 아이템이 풀렸음을 이력으로 남긴다 
        self._events.append(
            ItemEvent(
                ItemEventType.UNLISTED,
                self.owner_id,
                self.owner_id,
                now,
                actor_id=by_owner_id,
                listing_id=listing_id
            )
        )

    def transfer_to(
            self,
            new_owner_id: int,
            now: datetime,
            listing_id: int | None=None,
            trade_id: int | None=None,
            resale_delay: timedelta = DEFAULT_RESALE_DELAY,
    ) -> None:
        _check_id('new_owner_id', new_owner_id)
        _check_now(now)

        # 아이템이 잠겨있거나 이미 그 소유자인 경우 소유권 이전 불가
        if self.status != ItemStatus.LISTED or new_owner_id == self.owner_id:
            raise InvalidStateError()
        # 원소유자가 전소유자가 된다
        previous_owner_id = self.owner_id
        # 새소유자가 진소유자가 된다
        self.owner_id = new_owner_id
        # 아이템은 소유 상태가 되고 
        self.status = ItemStatus.OWNED
        # 소유권 이전 시각을 기록하고
        self.acquired_at = now
        # 새소유자의 아이템 획득 출처는 거래가 된다.
        self.origin = ItemOrigin.TRADE
        self.resale_available_at = now + resale_delay
        self._events.append(
            ItemEvent(
                ItemEventType.TRANSFERRED,
                # from
                previous_owner_id,
                # to
                new_owner_id,
                now,
                listing_id=listing_id,
                trade_id=trade_id,
            )
        )

    # 그동안 쌓인 이력(_events)을 레포지토리가 꺼내갈 수 있도록 만든 메서드
    # -> 도메인은 DB를 모르니까 메서드를 만들어 놓고 외부에서 가져다 쓰도록 하기 위함
    def pop_events(self) -> list[ItemEvent]:
        # 그동안 쌓인 이력(_events)을 보내고(return events) 새 이력 리스트 초기화
        events, self._events = self._events, []
        return events

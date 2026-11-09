"""아이템 카탈로그(ItemDefinition): 서버 카탈로그에 있는 아이템의 공통 정보

- 누구의 소유물도 아니다. 사용자가 가진 개별 아이템(InventoryItem)과 구분한다
- code는 고유하고 ^[a-z][a-z0-9_]{2,49}$ 형식, name은 공백 제외 1~100자다
- category는 FISH/GEM/MISC, rarity는 COMMON~LEGENDARY만 허용한다
- start_price는 0보다 큰 정수, weight는 0 이상의 정수, icon은 영문 소문자로 시작하고 영문 소문자·숫자·밑줄만 쓴 1~50자다
- name과 category는 만든 뒤 바꿀 수 없다 (바꾸려 하면 도메인이 거절한다)
- start_price가 바뀌어도 이미 등록된 매물에는 영향이 없다 (매물이 등록 때 복사해 간다)
- id는 저장소가 DB에 저장할 때 정해진다. 만들 때는 비어 있고, 규칙 검사 대상이 아니다
- 순수 파이썬만 쓴다 (FastAPI, Pydantic, SQLAlchemy, logging을 import하지 않는다)
"""

import re

from inventory.domain.enums import ItemCategory, ItemRarity
from inventory.domain.exceptions import (
    DefinitionImmutableFieldError,
    ItemRuleViolationError
)

_CODE_PATTERN = re.compile(r'^[a-z][a-z0-9_]{2,49}$')
_ICON_PATTERN = re.compile(r'^[a-z][a-z0-9_]{0,49}$')

def _check_code(code) -> str:
    if not isinstance(code, str) or not _CODE_PATTERN.fullmatch(code):
        raise ItemRuleViolationError(
            'code는 영문 소문자로 시작해 숫자, 언더바를 포함한 3~50자 이내여야 합니다.'
        )
    return code

def _check_name(name) -> str:
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ItemRuleViolationError(
            'name은 공백을 제외하고 1~100자 이내여야 합니다.'
        )
    return name.strip()

def _check_enum(enum_class, field: str, value):
    if value not in enum_class:
        raise ItemRuleViolationError(f'{field}는 허용된 값이 아닙니다.')
    return enum_class(value)

def _check_int(field: str, value, minimum: int) -> int:
    # bool은 int의 자식이고 True가 1로 통과하므로 따로 체크
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ItemRuleViolationError(f'{field}는 {minimum} 이상의 정수여야 합니다.')
    return value

def _check_icon(icon) -> str:
    # 그림 파일 이름이 주소에 그대로 쓰이므로 허용할 값을 1차 방어
    if not isinstance(icon, str) or not _ICON_PATTERN.fullmatch(icon):
        raise ItemRuleViolationError('icon은 영문 소문자로 시작작하고 숫자와 언더바를 포함한 1~50자 이내여야 합니다.')
    return icon

def _check_fishable(fishable) -> bool:
    if not isinstance(fishable, bool):
        raise ItemRuleViolationError('fishable은 참/거짓이어야 합니다.')
    return fishable

class ItemDefinition:
    def __init__(
            self,
            code: str,
            name: str,
            category: ItemCategory | str,
            rarity: ItemRarity | str, 
            start_price: int,
            description: str = '',
            icon: str = 'default',
            weight: int = 10,
            fishable: bool = True,
            id: int | None=None # DB 조회용 
    ) -> None:
        self.id = id # DB 조회용
        # 아래 property로만 읽게 해서 name.category 수정에 제약을 둠
        self._code = _check_code(code)
        self._name = _check_name(name)
        self._category = _check_enum(ItemCategory, 'category', category)
        self._rarity = _check_enum(ItemRarity, 'rarity', rarity)
        self.start_price = _check_int('start_price', start_price, 1)
        self.description = description
        self.icon = _check_icon(icon)
        self.weight = _check_int('weight', weight, 0)
        self.fishable = _check_fishable(fishable)

    @property
    def code(self) -> str:
        return self._code

    @property
    def name(self) -> str:
        return self._name

    @property
    def category(self) -> ItemCategory:
        return self._category

    @property
    def rarity(self) -> ItemRarity:
        return self._rarity

    def update(
            self,
            *,
            name: str | None=None,
            category: ItemCategory | str | None=None,
            weight: int | None=None,
            fishable: bool | None=None,
            icon: str | None=None,
            description: str | None=None,
            start_price: int | None=None,
    ) -> None:
        # name.category는 생성 후 수정 불가 (값이 같아도 거절)
        if name is not None or category is not None:
            raise DefinitionImmutableFieldError()

        # 전부 검사해서 모아두고 전부 유효할 때만 반영
        changes = {}

        if start_price is not None:
            changes['start_price'] = _check_int('start_price', start_price, 1)
        if weight is not None:
            changes['weight'] = _check_int('weight', weight, 0)
        if icon is not None:
            changes['icon'] = _check_icon(icon)
        if fishable is not None:
            changes['fishable'] = _check_fishable(fishable)
        if description is not None:
            changes['description'] = description

        for field, value in changes.items():
            setattr(self, field, value)
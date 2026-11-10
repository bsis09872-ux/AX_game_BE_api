"""내 인벤토리 화면의 필터와 주소 만들기

- 화면 라우터(web_router.py)가 쓰는 도우미다. 서비스·DB를 모르고, 받은 값으로 글자(주소, 버튼 데이터)만 만든다
- 필터 줄은 상태, 분류, 희귀도, 정렬 네 묶음이다. 버튼 하나는 값 하나만 바꾸고 나머지 필터는 유지하며, 쪽은 1쪽으로 돌아간다 (주소에 page를 넣지 않는다)
- 기본 정렬(최근 획득순)은 주소에 넣지 않는다
- 허용값(Status, Category, Rarity, InventorySort)은 API 라우터(router.py)와 같은 것을 쓴다
- 도감은 필터가 분류·희귀도 두 가지뿐이라 템플릿에서 직접 주소를 만든다. 이 파일은 값이 네 개이고 쪽까지 있는 내 인벤토리 목록용이다
"""

from typing import get_args
from urllib.parse import urlencode

from inventory.presentation.router import Category, InventorySort, Rarity, Status

# 정렬을 안 정했을 때의 기본값 (주소에는 넣지 않는다)
DEFAULT_SORT = 'acquired_desc'
CATEGORY_LABELS = {'FISH': '물고기', 'GEM': '보석', 'MISC': '잡화'}
STATUS_LABELS = {'OWNED': '보관 중', 'LISTED': '경매 중'}
SORT_LABELS = {'acquired_desc': '최근 획득 순', 'rarity_desc': '희귀도 높은 순', 'name_asc': '이름 오름차순'}


# 내 인벤토리 주소: 값이 있는 것만 붙인다
def inventory_href(*, status=None, category=None, rarity=None, sort=DEFAULT_SORT, page=None, item=None) -> str:
    params = {}
    if status:
        params['status'] = status
    if category:
        params['category'] = category
    if rarity:
        params['rarity'] = rarity
    # 기본 정렬은 주소에 넣지 않는다
    if sort != DEFAULT_SORT:
        params['sort'] = sort
    if page is not None:
        params['page'] = page
    # 선택한 아이템: 가방 칸을 누르면 오른쪽 패널에 보여 준다
    if item is not None:
        params['item'] = item
    return '/inventory' + ('?' + urlencode(params) if params else '')


# 내 인벤토리 필터 묶음 (상태, 분류, 희귀도, 정렬)
def filter_groups(status, category, rarity, sort) -> list[dict]:
    current = {'status': status, 'category': category, 'rarity': rarity, 'sort': sort}

    # 값 하나만 바꾼 주소를 가진 버튼 한 개. value가 None이면 '전체' 버튼이다
    def option(key, value, text, css=''):
        return {
            'text': text,
            'href': inventory_href(**{**current, key: value}),
            'current': current[key] == value,
            'css': css,
        }

    return [
        {'label': '상태', 'options': [option('status', None, '전체')]
            + [option('status', v, STATUS_LABELS[v]) for v in get_args(Status)]},
        {'label': '분류', 'options': [option('category', None, '전체')]
            + [option('category', v, CATEGORY_LABELS.get(v, v)) for v in get_args(Category)]},
        {'label': '희귀도', 'options': [option('rarity', None, '전체')]
            + [option('rarity', v, v, f'rarity-{v}') for v in get_args(Rarity)]},
        {'label': '정렬', 'options': [option('sort', v, SORT_LABELS[v], 'equal-width' if v == DEFAULT_SORT else '') for v in get_args(InventorySort)]},
    ]

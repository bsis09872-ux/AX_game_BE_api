# [Claude] 이 파일은 Claude가 작성함 (검토 전)
"""경매 화면이 쓰는 주소 만들기와 화면용 값 계산

- 서비스·DB를 모르고, 받은 값으로 글자(주소, 문구)와 숫자만 만든다
- 화면 URL은 담당자 결정 대기: 주소 문자열은 이 파일의 함수와 web_router.py의 데코레이터에만 둔다
- embed=1은 팝업(iframe) 안에서 보일 때 붙는다. 팝업 안의 링크는 모두 이 파일의 함수로 만들어 embed를 유지한다
"""

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode

from auction.domain.listings.entities import Listing


# region [Claude] 주소 만들기
# 값이 None인 것은 주소에 넣지 않는다
def _url(path: str, embed: bool = False, **params) -> str:
    query = {key: value for key, value in params.items() if value is not None}
    if embed:
        query['embed'] = 1
    return path + ('?' + urlencode(query) if query else '')


def list_url(page: int = 1, embed: bool = False) -> str:
    return _url('/auctions', embed, page=page if page > 1 else None)


def detail_url(listing_id: int, embed: bool = False, ok: str | None = None) -> str:
    return _url(f'/auctions/{listing_id}', embed, ok=ok)


def new_url(item_id: int | None = None, embed: bool = False) -> str:
    return _url('/auctions/new', embed, item=item_id)


def trades_url(tab: str = 'won', page: int = 1) -> str:
    return _url('/auctions/trades', False, tab=tab if tab != 'won' else None, page=page if page > 1 else None)


# 폼이 보내는 주소 (POST)
def register_action(embed: bool = False) -> str:
    return _url('/auctions/new', embed)


def bid_action(listing_id: int, embed: bool = False) -> str:
    return _url(f'/auctions/{listing_id}/bid', embed)


def cancel_action(listing_id: int, embed: bool = False) -> str:
    return _url(f'/auctions/{listing_id}/cancel', embed)
# endregion


# region [Claude] 알림 문구
# 성공 후 이동한 화면의 ?ok= 값을 고정 문구로만 바꾼다 (주소에 적힌 글자를 그대로 보여 주지 않는다)
NOTICES = {
    'started': '경매가 시작됐어요!',
    'queued': '같은 아이템이 경매 중이라 순서를 기다려요.',
    'bid': '입찰했어요!',
    'cancelled': '경매를 취소했어요.',
}


def notice_text(code: str | None) -> str | None:
    return NOTICES.get(code) if code else None
# endregion


# region [Claude] 익명 입찰자
# 입찰자 ID는 공개하지 않는다. 문구는 매물 번호와 현재 입찰가로 고르므로 같은 사람이 여러 매물에서 같은 별명으로 보이지 않는다
# 그림 번호는 문구 번호와 짝이다 (static/sprites/npc_bidder_{번호}.png)
ALIASES = (
    '수상한 낚시꾼',
    '정체불명의 입찰자',
    '복면 쓴 수집가',
    '지나가던 큰손',
    '물수제비 장인',
    '소문난 낚시꾼',
    '비밀스러운 강태공',
    '미끼를 문 누군가',
)


# 반환: (그림 번호 1~8, 별명)
def alias_for(listing_id: int, bid_amount: int) -> tuple[int, str]:
    index = (listing_id + bid_amount) % len(ALIASES)
    return index + 1, ALIASES[index]
# endregion


# 남은 시간(초)을 m:ss로 보여 준다
def format_clock(seconds: int) -> str:
    minutes, rest = divmod(max(seconds, 0), 60)
    return f'{minutes}:{rest:02d}'


# region [Claude] 아이템 표시
CATEGORY_LABELS = {'FISH': '물고기', 'GEM': '보석', 'MISC': '잡화'}


# 화면에 보여 줄 아이템 정보. inventory/_macros.html의 item_icon이 icon·rarity를 읽는다
@dataclass(frozen=True)
class ItemView:
    name: str
    category: str
    rarity: str
    icon: str


# 아이템을 못 읽을 때(지워진 아이템 등) 대신 보여 준다
UNKNOWN_ITEM = ItemView(name='알 수 없는 아이템', category='', rarity='COMMON', icon='gift_box')


# 인벤토리의 아이템 정보(ItemInfo)에서 화면에 필요한 값만 골라낸다
def item_view(info) -> ItemView:
    definition = info.definition
    return ItemView(
        name=definition.name,
        category=CATEGORY_LABELS.get(definition.category, definition.category),
        rarity=definition.rarity,
        icon=definition.icon,
    )
# endregion


# region [Claude] 경매장 목록 카드
# 남은 시간이 이 값(초) 이하면 급하다는 표시를 한다
URGENT_SECONDS = 60


@dataclass(frozen=True)
class ListingCard:
    id: int
    href: str
    item: ItemView
    seller_name: str
    price: int  # 입찰이 없으면 시작가
    has_bid: bool
    remaining_seconds: int
    remaining_text: str
    urgent: bool


def card_view(listing: Listing, item: ItemView, seller_name: str, now: datetime, embed: bool = False) -> ListingCard:
    remaining = listing.remaining(now)
    seconds = int(remaining.total_seconds()) if remaining is not None else 0
    return ListingCard(
        id=listing.id,
        href=detail_url(listing.id, embed),
        item=item,
        seller_name=seller_name,
        price=listing.current_bid_amount or listing.start_price,
        has_bid=listing.has_bidder(),
        remaining_seconds=seconds,
        remaining_text=format_clock(seconds),
        urgent=seconds <= URGENT_SECONDS,
    )
# endregion

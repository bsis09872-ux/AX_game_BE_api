# [Claude] 이 파일은 Claude가 작성함 (검토 전)
"""경매 화면이 쓰는 주소 만들기와 화면용 값 계산

- 서비스·DB를 모르고, 받은 값으로 글자(주소, 문구)와 숫자만 만든다
- 화면 URL은 담당자 결정 대기: 주소 문자열은 이 파일의 함수와 web_router.py의 데코레이터에만 둔다
- embed=1은 팝업(iframe) 안에서 보일 때 붙는다. 팝업 안의 링크는 모두 이 파일의 함수로 만들어 embed를 유지한다
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlencode

from auction.domain.listings.entities import AUCTION_DURATION, Listing, ListingStatus


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
UNKNOWN_ITEM = ItemView(name='알 수 없는 아이템', category='', rarity='COMMON', icon='unknown')


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


# region [Claude] 경매 상세
STATUS_LABELS = {
    ListingStatus.BIDDING: '입찰 중',
    ListingStatus.QUEUED: '대기 중',
    ListingStatus.SOLD: '낙찰',
    ListingStatus.FAILED: '유찰',
    ListingStatus.CANCELLED: '취소',
}

# 진행 바에 점을 찍는 중요한 지점 (남은 시간, 초): 절반, 마감 임박, 마감
TIMEBAR_MARKS = (180, 60, 0)


@dataclass(frozen=True)
class TimebarMark:
    left: float  # 바 왼쪽 끝에서의 위치(%). 남은 시간이 이 지점이면 채워진 부분의 끝이 여기에 닿는다
    passed: bool  # 남은 시간이 이 지점에 이르렀거나 지났는지
    label: str


@dataclass(frozen=True)
class Timebar:
    percent: float  # 채워진 부분(남은 시간 비율)
    urgent: bool
    remaining: int
    total: int
    marks: tuple[TimebarMark, ...]


# 남은 시간(초)으로 진행 바를 만든다. 바는 남은 시간만큼 채워져 점점 줄어든다
def timebar_view(remaining_seconds: int) -> Timebar:
    total = int(AUCTION_DURATION.total_seconds())
    remaining = min(max(remaining_seconds, 0), total)
    marks = tuple(
        TimebarMark(left=round(mark / total * 100, 2), passed=remaining <= mark, label=format_clock(mark))
        for mark in TIMEBAR_MARKS
    )
    return Timebar(
        percent=round(remaining / total * 100, 2),
        urgent=remaining <= URGENT_SECONDS,
        remaining=remaining,
        total=total,
        marks=marks,
    )


# 결과 배너 (낙찰, 유찰, 취소, 대기). 입찰 중에는 없다
@dataclass(frozen=True)
class Banner:
    kind: str  # 'sold', 'fail', 'cancel', 'queued'
    title: str
    sub: str


def banner_view(listing: Listing, viewer_id: int, winner_name: str) -> Banner | None:
    if listing.status == ListingStatus.SOLD:
        price = f'{listing.current_bid_amount:,}'
        if listing.current_bidder_id == viewer_id:
            return Banner('sold', '축하해요, 낙찰!', f'{price} G · 아이템이 가방으로 들어갔어요')
        if listing.seller_id == viewer_id:
            return Banner('sold', '팔렸어요!', f'{price} G에 {winner_name}님이 낙찰받았어요')
        return Banner('sold', f'낙찰! {winner_name}', f'{price} G에 낙찰됐어요')
    if listing.status == ListingStatus.FAILED:
        return Banner('fail', '유찰…', '입찰자가 없어서 아이템이 판매자에게 돌아갔어요')
    if listing.status == ListingStatus.CANCELLED:
        return Banner('cancel', '경매 취소', '판매자가 경매를 취소했어요')
    if listing.status == ListingStatus.QUEUED:
        return Banner('queued', '대기 중', '같은 아이템이 경매 중이라 순서를 기다려요')
    return None


# 무대에 서는 1등(입찰 중) 또는 낙찰자(낙찰). 입찰 중에는 익명 별명, 내가 1등이면 "나"
@dataclass(frozen=True)
class Leader:
    sprite: int
    label: str
    badge: str
    amount: int


def leader_view(listing: Listing, viewer_id: int, winner_name: str) -> Leader | None:
    if not listing.has_bidder() or listing.status not in (ListingStatus.BIDDING, ListingStatus.SOLD):
        return None
    sprite, alias = alias_for(listing.id, listing.current_bid_amount)
    is_me = listing.current_bidder_id == viewer_id
    if listing.status == ListingStatus.SOLD:
        return Leader(sprite, '나' if is_me else winner_name, '낙찰!', listing.current_bid_amount)
    return Leader(sprite, '나' if is_me else alias, '1등', listing.current_bid_amount)


@dataclass(frozen=True)
class DetailView:
    id: int
    item: ItemView
    status: str
    status_label: str
    seller_name: str
    price: int
    price_label: str
    has_bid: bool
    min_bid: int  # 이 금액 이상으로 입찰해야 한다
    ends_at: datetime | None
    remaining_text: str
    timebar: Timebar | None
    leader: Leader | None
    banner: Banner | None
    message: str  # 입찰 패널의 내 상태 안내
    can_bid: bool
    can_cancel: bool
    is_seller: bool
    bid_action: str
    cancel_action: str
    list_href: str


def detail_view(
    listing: Listing,
    viewer_id: int,
    now: datetime,
    item: ItemView,
    seller_name: str,
    winner_name: str,
    blocked_seconds: int | None,
    embed: bool = False,
) -> DetailView:
    bidding = listing.status == ListingStatus.BIDDING
    is_seller = listing.seller_id == viewer_id
    is_leader = listing.current_bidder_id == viewer_id

    remaining = listing.remaining(now)
    seconds = int(remaining.total_seconds()) if remaining is not None else 0
    blocked = bidding and blocked_seconds is not None and blocked_seconds > 0

    if not bidding:
        message = ''
    elif is_seller:
        message = '내 매물이에요. 입찰할 수 없어요.'
    elif is_leader:
        message = '지금 내가 1등이에요! 다른 사람이 더 높게 부르면 밀려나요.'
    elif blocked:
        message = f'연속 낙찰 제한 중이라 입찰할 수 없어요. (남은 시간 {format_clock(blocked_seconds)})'
    elif listing.has_bidder():
        message = '지금은 다른 입찰자가 1등이에요.'
    else:
        message = '아직 입찰이 없어요. 첫 입찰을 해 보세요!'

    if listing.status == ListingStatus.SOLD:
        price_label = '낙찰가'
    else:
        price_label = '현재가' if listing.has_bidder() else '시작가'

    return DetailView(
        id=listing.id,
        item=item,
        status=listing.status.value,
        status_label=STATUS_LABELS[listing.status],
        seller_name=seller_name,
        price=listing.current_bid_amount or listing.start_price,
        price_label=price_label,
        has_bid=listing.has_bidder(),
        min_bid=(listing.current_bid_amount or listing.start_price) + 1,
        ends_at=listing.ends_at,
        remaining_text=format_clock(seconds) if bidding else '마감',
        timebar=timebar_view(seconds) if bidding else None,
        leader=leader_view(listing, viewer_id, winner_name),
        banner=banner_view(listing, viewer_id, winner_name),
        message=message,
        can_bid=bidding and seconds > 0 and not is_seller and not is_leader and not blocked,
        can_cancel=listing.status == ListingStatus.QUEUED and is_seller,
        is_seller=is_seller,
        bid_action=bid_action(listing.id, embed),
        cancel_action=cancel_action(listing.id, embed),
        list_href=list_url(1, embed),
    )
# endregion


# region [Claude] 경매 등록
# 금액·번호 입력을 숫자로 바꾼다. 숫자가 아니거나 0 이하이거나 너무 크면 None
MAX_INPUT_NUMBER = 10**12


def parse_number(text: str) -> int | None:
    cleaned = (text or '').strip().replace(',', '')
    if not cleaned.isdigit():
        return None
    value = int(cleaned)
    return value if 1 <= value <= MAX_INPUT_NUMBER else None


@dataclass(frozen=True)
class NewView:
    item_id: int
    item: ItemView
    start_price: int  # 아이템 카탈로그의 시작가. 사용자가 바꿀 수 없다
    can_register: bool
    reason: str  # 올릴 수 없을 때의 이유
    action: str
    back_href: str


# 인벤토리의 아이템 정보(ItemInfo)로 등록 화면에 보여 줄 값을 만든다
def new_view(info, now: datetime, embed: bool = False) -> NewView:
    reason = ''
    resale_at = info.resale_available_at
    if info.status != 'OWNED':
        reason = '이미 경매에 올라가 있는 아이템이에요.'
    elif resale_at is not None:
        # 시각이 시간대 없이 저장돼 있어도 UTC로 보고 비교한다
        aware = resale_at if resale_at.tzinfo is not None else resale_at.replace(tzinfo=timezone.utc)
        if aware > now:
            reason = f'아직 다시 팔 수 없어요. ({aware.strftime("%Y-%m-%d %H:%M:%S")} UTC 이후)'
    return NewView(
        item_id=info.id,
        item=item_view(info),
        start_price=info.definition.start_price,
        can_register=not reason,
        reason=reason,
        action=register_action(embed),
        back_href=list_url(1, embed),
    )
# endregion


# region [Claude] 내 거래 (낙찰받은 것, 판매한 것)
TRADE_TABS = {'won': '낙찰받은 것', 'sold': '판매한 것'}


@dataclass(frozen=True)
class TradeRow:
    href: str
    item_name: str
    partner_name: str  # 낙찰받은 것이면 판매자, 판매한 것이면 구매자
    price: int
    completed_at: datetime


# 거래 기록의 체결 당시 이름 스냅샷으로 표의 줄을 만든다
def trade_rows(trades, tab: str) -> list[TradeRow]:
    return [
        TradeRow(
            href=detail_url(trade.listing_id),
            item_name=trade.item_name_snapshot,
            partner_name=trade.seller_name_snapshot if tab == 'won' else trade.buyer_name_snapshot,
            price=trade.price_snapshot,
            completed_at=trade.completed_at,
        )
        for trade in trades
    ]


# 입찰 제한 상태 (최근 낙찰 횟수와 제한 중이면 남은 시간)
@dataclass(frozen=True)
class LimitView:
    count: int
    max_count: int
    blocked: bool
    remaining_text: str


def limit_view(state) -> LimitView:
    return LimitView(
        count=state.purchase_count,
        max_count=state.max_count,
        blocked=state.is_blocked,
        remaining_text=format_clock(int(state.remaining.total_seconds())),
    )
# endregion

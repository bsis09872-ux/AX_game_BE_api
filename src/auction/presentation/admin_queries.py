from typing import Annotated
from urllib.parse import urlencode

from pydantic import BaseModel, BeforeValidator, Field

from auction.application.admin_dto import AdminListingStatus


def empty_to_none(value):
    # GET 폼의 비워 둔 검색 항목은 조건을 지정하지 않은 것으로 처리한다.
    return None if value == '' else value


OptionalId = Annotated[
    int | None, Field(ge=1, le=9223372036854775807), BeforeValidator(empty_to_none),
]
OptionalStatus = Annotated[AdminListingStatus | None, BeforeValidator(empty_to_none)]


class AdminAuctionQuery(BaseModel):
    page: int = Field(default=1, ge=1, le=2147483647)

    def filters(self) -> dict:
        return self.model_dump(exclude={'page'}, exclude_none=True)

    def page_url(self, path: str, page: int | None = None) -> str:
        params = self.filters()
        params['page'] = self.page if page is None else page
        return f'{path}?{urlencode(params)}'


class AdminListingQuery(AdminAuctionQuery):
    listing_id: OptionalId = None
    item_definition_id: OptionalId = None
    inventory_item_id: OptionalId = None
    status: OptionalStatus = None


class AdminTradeQuery(AdminAuctionQuery):
    listing_id: OptionalId = None
    buyer_id: OptionalId = None
    seller_id: OptionalId = None

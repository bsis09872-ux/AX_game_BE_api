from typing import Protocol

from auth.application.admin_dto import AdminListing


# TODO(지갑 담당): 회원별 잔액과 페이지별 거래 내역의 조회 계약/factory를 제공하면
# 관리자 지갑 조회에 연결한다. 현재 main에는 호출할 지갑 서비스가 없다.


class AdminAuctionReader(Protocol):
    """관리자 화면에서 사용하는 경매 조회 계약. 상태 변경과 commit은 수행하지 않는다."""

    async def list_bidding(self, page: int) -> tuple[list[AdminListing], bool]: ...

    async def get_listing(self, listing_id: int) -> AdminListing: ...

    # TODO(경매 담당): 전체 상태별 목록/검색과 관리자 취소 전용 서비스를 제공하면
    # 계약을 확장한다. 현재 목록은 BIDDING만, ID 조회는 모든 상태를 조회한다.
    # 판매자 취소와 관리자 강제 취소는 같은 기능으로 취급하지 않는다.

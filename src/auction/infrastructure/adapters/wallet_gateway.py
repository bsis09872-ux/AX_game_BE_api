# Adapter: Auction의 지갑 계약을 Wallet 서비스에 연결한다.
# 잔액 계산과 잠금은 Wallet이 담당하고, commit·rollback은 호출자가 담당한다.

from auction.application.contract import WalletGateway
from wallet.application.service import WalletService


class WalletGatewayAdapter(WalletGateway):
    # Auction과 같은 세션으로 구성한 Wallet 서비스를 받는다.
    def __init__(self, wallet_service: WalletService) -> None:
        self._wallet_service = wallet_service

    # 입찰액과 변경 전 최고 입찰 정보를 전달해 자금 검사를 요청한다.
    # 정상 종료하면 검사 통과다. 잔액 부족 등의 예외는 그대로 전달한다.
    async def check_bid_funds(
        self,
        *,
        bidder_id: int,
        amount: int,
        current_bidder_id: int | None,
        current_bid_amount: int | None,
    ) -> None:
        await self._wallet_service.check_bid_funds(
            bidder_id=bidder_id,
            amount=amount,
            current_bidder_id=current_bidder_id,
            current_bid_amount=current_bid_amount,
        )

    # 구매자·판매자·낙찰가를 전달해 재화 이전을 요청한다.
    # 반환값은 사용하지 않는다. 실패하면 예외를 전달해 전체 rollback하게 한다.
    async def settle_sale(
        self,
        *,
        buyer_id: int,
        seller_id: int,
        price: int,
    ) -> None:
        await self._wallet_service.settle_sale(
            buyer_id=buyer_id,
            seller_id=seller_id,
            price=price,
        )

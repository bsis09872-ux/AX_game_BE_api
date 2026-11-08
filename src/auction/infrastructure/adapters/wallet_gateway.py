# Wallet Adapter: 경매의 WalletGateway 계약을 wallet 서비스에 연결한다.
# [TO DO] Wallet이 main에 반영되면 check_bid_funds·settle_sale에 연결한다. (진행 전)
# 그 전까지는 호출하면 미구현 오류를 낸다.

from auction.application.contract import WalletGateway


class WalletGatewayAdapter(WalletGateway):

    async def has_balance(
        self,
        user_id: int,
        amount: int,
    ) -> bool:
        raise NotImplementedError("wallet 반영 후 연결한다.")

    async def transfer(
        self,
        from_user_id: int,
        to_user_id: int,
        amount: int,
    ) -> None:
        raise NotImplementedError("wallet 반영 후 연결한다.")

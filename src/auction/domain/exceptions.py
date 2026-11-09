# 경매 도메인 예외: 화면이 code로 구분해 처리해야 하는 경우만 정의한다.
# 그 외에는 공통 예외(BusinessRuleError 등)에 메시지만 넘긴다.
# 상태 코드는 팀 공통 핸들러가 부모 분류로 정한다.

from shared.core.exceptions import ConflictError, ForbiddenError


# 409: 마감 시각이 지난 매물에 입찰. 화면은 입찰창을 닫는다.
class AuctionEndedError(ConflictError):
    code: str = "AUCTION_ENDED"
    message: str = "입찰 시간이 종료되었습니다."


# 409: 현재 최고가 이하로 입찰 (동시 입찰로 밀린 경우 포함). 화면은 현재가를 다시 조회한다.
class BidNotHigherError(ConflictError):
    code: str = "BID_NOT_HIGHER"
    message: str = "현재 최고 입찰가보다 높게 입찰해야 합니다."


# 403: 연속 낙찰 제한 중 새 입찰. 화면은 제한 상태(bid-limit)를 조회해 남은 시간을 보여 준다.
# [TO DO] 입찰 서비스 구현 시 제한 판단 후 발생시킨다. (진행 전)
class BidBannedError(ForbiddenError):
    code: str = "BID_BANNED"
    message: str = "연속 낙찰 제한으로 잠시 입찰할 수 없습니다."

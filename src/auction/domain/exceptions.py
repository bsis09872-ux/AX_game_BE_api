# 경매 도메인 예외: 화면이 code로 구분해 처리해야 하는 경우만 정의한다.
# 그 외에는 공통 예외(BusinessRuleError 등)에 메시지만 넘긴다.
# 상태 코드는 팀 공통 핸들러가 부모 분류로 정한다.

from shared.core.exceptions import ConflictError, ForbiddenError, AppError


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


# 500: 매물과 인벤토리 아이템의 상태가 서로 맞지 않는 내부 데이터 불일치.
# 사용자 잘못이 아니므로 400·403·404·409 분류(자식 클래스)를 쓰지 않는다.
# 공통 핸들러가 분류되지 않은 AppError로 보고 500 공통 형식으로 응답한다.
# 원래 예외 유형과 관련 ID 로그는 Inventory Adapter가 변환할 때 남긴다.
class InventoryMismatchError(AppError):
    code: str = "AUCTION_INVENTORY_MISMATCH"
    message: str = "서버 내부 오류가 발생했습니다."

# auction / application

등록·입찰·취소·정산의 실행 순서를 조율한다. 현재 서비스 파일은 구현 전 작업 주석이다.

## 파일 역할

- `listings/service.py`: 매물 등록·조회·입찰·취소.
- `trades/service.py`: 내 낙찰·판매 내역과 참여 제한 상태 조회.
- [TO DO] `constructs.py`: 외부 도메인 연결 인터페이스 정의.
- [TO DO] `auction_service.py`: 마감·정산·Trade 생성·제한 상태 갱신·다음 매물 공개.

## 정산 순서

1. 합의한 잠금 순서로 매물과 사용자·자산 상태를 조회하고 종료 여부를 재검사한다.
2. 입찰자가 없으면 유찰과 아이템 예약 해제를 처리한다.
3. 입찰자가 있으면 재화·아이템 이전 후 SOLD 처리와 Trade 저장을 진행한다.
4. 이번 Trade.completed_at을 포함하여 B 정책을 계산하고 User 제한 상태를 갱신한다.
5. 다음 대기 매물 공개를 조율하고 전체 성공 시 commit한다.

제한 중 기존 입찰이 낙찰돼도 정산한다. 기술적 오류는 전체 rollback하며 무조건 유찰로 바꾸지 않는다.

## 외부 계약 요청

- [TO DO] User 담당자: `get_auction_state_for_update(user_id: int) -> AuctionState | None` 제공 협의. AuctionState는 횟수와 blocked_until을 전달하는 제안 DTO다.
- [TO DO] User 담당자: `update_auction_state(user_id: int, purchase_count: int, blocked_until: datetime | None) -> None` 제공 협의.
- [TO DO] 두 메서드는 async이며 같은 주입 세션을 사용하고 내부 commit하지 않는 계약이 필요하다. 현재 User Repository에는 없다.
- [TO DO] inventory 담당자: 예약·예약 해제·소유권 이전의 공개 인터페이스와 실패 예외 합의.
- [TO DO] wallet 담당자: 잔액 조회·잠금·입출금 계약 합의. 현재 Auction은 최고 입찰액 합산 방식이다.
- [TO DO] 모든 담당자: 잠금 순서·세션 공유·commit 주체·동시 정산 방식을 합의한다.
- [TO DO] 앱 담당자: 모델·라우터·마감 실행 등록 요청. Auction 밖 파일은 수정하지 않는다.

## 정책과 응답

- 공통 BusinessRuleError는 현재 400으로 변환된다. 새 예외 체계나 403 분기는 추가하지 않는다.
- 남은 시간 메시지는 정책 결과를 사용한다. 정책 함수가 HTTP 응답을 만들지 않는다.

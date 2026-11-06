# 로그인 사용자의 낙찰·판매 내역과 경매 참여 제한 상태를 조회한다.
# [TO DO] TradeRepository와 사용자 제한 상태 인터페이스를 생성자로 받는다.
# [TO DO] 인증 사용자 ID로 list_by_buyer / list_by_seller를 호출한다.
# [TO DO] Trade 기록과 보존된 blocked_until을 읽고 domain의 B 정책을 호출한다.
# [TO DO] 유효 횟수·최대 3회·제한 여부·차단 종료 시각·남은 초를 반환한다.
# [TO DO] 만료 후 횟수 동기화는 사용자 잠금 아래 처리하고 blocked_until은 지우지 않는다.
# 거래는 불변 기록이다. 이 파일에 거래 수정·삭제나 직접 정산 SQL을 넣지 않는다.
# [TO DO] 정산·Trade 생성·제한 상태 갱신은 별도 application/auction_service.py에서 조율한다.

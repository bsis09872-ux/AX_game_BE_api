# auction / presentation

HTTP 요청을 검증하고 application 결과를 응답으로 변환한다. 현재 파일은 구현 전 작업 주석이다.

## 폴더 역할

- `listings/router.py`: 목록·상세·등록·입찰·취소 요청 연결.
- `listings/schemas.py`: 매물 요청·응답 스키마.
- `trades/router.py`: 내 낙찰·판매 내역과 제한 상태 조회 연결.
- `trades/schemas.py`: 거래 스냅샷·참여 제한 상태 응답.

## 연결할 것

- [TO DO] 인증 사용자와 서비스 의존성을 주입한다.
- [TO DO] URI·응답 형식·페이지 계약을 확정한다. 현재 앱 접두사는 /v1이다.
- UTC ISO 8601로 시각을 반환하며 KST 표시는 화면이 담당한다.
- 입찰 제한 중에도 조회는 허용한다. 공통 예외는 전역 핸들러로 전달한다.
- SQL·정산·낙찰 제한 계산은 이 계층에 구현하지 않는다.

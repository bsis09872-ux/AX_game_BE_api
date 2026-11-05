# 전체 구조 힌트

```
요청 JSON
  → [presentation] 요청 스키마 검증 → 라우터
  → [application]  Service가 순서 지휘
  → [domain]       엔티티가 규칙 판단
  → [infrastructure] Repository: 엔티티 ↔ ORM 모델 변환, 세션으로 DB 작업
  → [application]  엔티티 반환
  → [presentation] 응답 스키마로 거르기 → 공통 응답 → JSON
(어디서든 raise → exception_handlers가 공통 실패 응답으로)
```

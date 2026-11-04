"""레포지토리: 도메인 객체를 DB에 저장하고 읽는다

- commit하지 않는다. flush까지만 하고 commit과 rollback은 서비스가 한다
- find_by_id_for_update는 SELECT ... FOR UPDATE로 행을 잠그고, 잠근 뒤의 최신 상태를 돌려준다
- save(item)은 아이템과 쌓인 이력(pop_events)을 같은 트랜잭션에 저장한다
- 이력은 추가와 조회만 있다 (수정이나 삭제하는 메서드를 만들지 않는다)
- 읽기 메서드는 DB 상태를 바꾸지 않는다
- 업무 규칙을 판정하지 않는다 (규칙은 도메인에 있다)
"""

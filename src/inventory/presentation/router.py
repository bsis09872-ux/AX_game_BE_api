"""APIRouter: 인벤토리·카탈로그 조회 (U8), 운영자 관리·이력 조회 (U10, U12), 낚시 (U11).

TODO(U8) prefix /api/v1
- GET /inventory, /inventory/{item_id}  (남의 아이템은 404)
- GET /item-definitions, /item-definitions/{id}
- Depends(get_db), 현재 사용자 id 의존성(임시 스텁 -> 1번 current_user)
- ValueError 계열 -> {"error":{"code","message","detail"}} 변환 (400/403/404/409/429/503)
- 아이템 생성 라우트는 만들지 않는다 (위조 방지 A4)
TODO(U10, 선택 S): /admin/item-definitions POST / PATCH / DELETE (운영자 확인 의존성)
TODO(U12, 선택 S): GET /admin/inventory/{item_id}/events (운영자만, 오래된 순, 페이지)
TODO(U11, 선택 S): POST /fishing/cast, 본문 없음, DEMO_FISHING_ENABLED일 때만 등록
- main.py 등록은 변경안만 제시
"""

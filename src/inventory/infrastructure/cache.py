"""순수 파이썬 TTL 인메모리 캐시 (U14, 기본 컷).

시간이 남을 때만 한다. 하지 않아도 필수·선택 범위에는 영향이 없다.

TODO(U14)
- get(key) / set(key, value) / invalidate_all()
- TTL은 config의 CACHE_TTL_SECONDS, 시간은 clock 인자로 주입(테스트용)
- 대상: 아이템 종류 목록·상세만. reserve/transfer 판정에는 쓰지 않는다
- 한계: 프로세스별 메모리 -> 멀티 워커 불일치, 재시작하면 소실 (단일 worker로 시연)
"""

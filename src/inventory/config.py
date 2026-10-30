"""환경변수 설정 (U4).

TODO(U4)
- os.environ에서 읽기 (추가 패키지 없음, 실행: uv run --env-file .env ...)
- DATABASE_URL, TEST_DATABASE_URL, LOCK_TIMEOUT_MS, RESALE_DELAY_SECONDS(기본 1800),
  SEED_ON_STARTUP(기본 false), DEMO_FISHING_ENABLED(기본 false), FISHING_COOLDOWN_SECONDS(기본 10),
  CACHE_TTL_SECONDS(U14)
- 숫자 변환·기본값 포함, 비밀값(비밀번호 등)에는 기본값을 두지 않는다
- .env는 커밋하지 않고 .env.example에 키 이름과 예시값만 둔다
"""

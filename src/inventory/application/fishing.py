"""낚시 지급 서비스 (U11, 선택 S).

클라이언트 작업자와 겹칠 수 있어 내 몫으로 남긴 대비용이다.

TODO(U11)
- FishingService.cast(user_id, now): 쿨다운 확인(10초, 서버 메모리, 단일 워커)
  -> 후보(fishable=True, weight>0) -> 가중치 무작위(rng 주입) -> grant_item(origin=REWARD, actor_id=user_id) -> commit
- 후보가 없으면 NoFishableDefinitionError, 쿨다운 안이면 FishingCooldownError
- 클라이언트는 결과를 지정하지 못한다 (위조 방지 A8)
- 설정: DEMO_FISHING_ENABLED, FISHING_COOLDOWN_SECONDS (config.py)
- presentation import 금지
"""

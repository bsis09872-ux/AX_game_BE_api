"""도메인 예외 (U1).

모두 ValueError 하위 클래스. presentation에서 HTTP로 변환한다.
- ItemRuleViolation              -> 400 ITEM_RULE_VIOLATION
- DefinitionImmutableFieldError  -> 400 DEFINITION_IMMUTABLE (이름·카테고리 변경 시도)
- NotOwnerError                  -> 403 NOT_OWNER (조회는 404)
- InvalidStateError              -> 409 ITEM_STATE_CONFLICT
- ResaleNotAvailableError        -> 409 RESALE_NOT_AVAILABLE (가능한 시각 포함)
- DefinitionInUseError           -> 409 DEFINITION_IN_USE
- DefinitionNotFoundError        -> 404 DEFINITION_NOT_FOUND
- FishingCooldownError           -> 429 FISHING_COOLDOWN
- NoFishableDefinitionError      -> 503 FISHING_NO_REWARD

순수 파이썬만 사용한다. fastapi / sqlalchemy / pydantic import 금지.
설계: inventory-domain 6장
"""

"""ItemDefinition: 아이템 종류의 공통 정보, 서버 카탈로그 (U2).

TODO(U2)
- Enum: ItemCategory(FISH/GEM/MISC), ItemRarity(COMMON~LEGENDARY, 순위 값으로 정렬)
- 필드: code, name, category, rarity, start_price, description, icon, weight, fishable
- __init__ 검증: code 형식, name 길이, start_price > 0, weight >= 0, Enum 값
- update(weight, fishable, icon, description, start_price): name·category 변경은 DefinitionImmutableFieldError
- 봉인·귀속·기간제·용량·거래 가능 여부는 없다 (다음 버전 후보)
- 설계: inventory-domain 3장

순수 파이썬만 사용한다. fastapi / sqlalchemy / pydantic import 금지.
"""

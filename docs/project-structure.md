# 프로젝트 구조 안내

[README로 돌아가기](../README.md)

## 전체 구조

현재 존재하는 파일과 폴더입니다. 내부·생성 파일은 생략했습니다. 각 항목을 누르면 해당 경로로 이동합니다.

- [docs/](../docs/)
  - [.gitkeep](../docs/.gitkeep)
  - [project-structure.md](../docs/project-structure.md)
- [src/](../src/)
  - [auth/](../src/auth/)
    - [application/](../src/auth/application/)
      - [__init__.py](../src/auth/application/__init__.py)
    - [domain/](../src/auth/domain/)
      - [__init__.py](../src/auth/domain/__init__.py)
    - [infrastructure/](../src/auth/infrastructure/)
      - [__init__.py](../src/auth/infrastructure/__init__.py)
    - [presentation/](../src/auth/presentation/)
      - [__init__.py](../src/auth/presentation/__init__.py)
    - [__init__.py](../src/auth/__init__.py)
  - [inventory/](../src/inventory/)
    - [application/](../src/inventory/application/)
      - [__init__.py](../src/inventory/application/__init__.py)
    - [domain/](../src/inventory/domain/)
      - [__init__.py](../src/inventory/domain/__init__.py)
    - [infrastructure/](../src/inventory/infrastructure/)
      - [__init__.py](../src/inventory/infrastructure/__init__.py)
    - [presentation/](../src/inventory/presentation/)
      - [__init__.py](../src/inventory/presentation/__init__.py)
    - [__init__.py](../src/inventory/__init__.py)
  - [listing/](../src/listing/)
    - [application/](../src/listing/application/)
      - [__init__.py](../src/listing/application/__init__.py)
    - [domain/](../src/listing/domain/)
      - [__init__.py](../src/listing/domain/__init__.py)
    - [infrastructure/](../src/listing/infrastructure/)
      - [__init__.py](../src/listing/infrastructure/__init__.py)
    - [presentation/](../src/listing/presentation/)
      - [__init__.py](../src/listing/presentation/__init__.py)
    - [__init__.py](../src/listing/__init__.py)
  - [static/](../src/static/)
    - [.gitkeep](../src/static/.gitkeep)
  - [templates/](../src/templates/)
    - [.gitkeep](../src/templates/.gitkeep)
  - [trading/](../src/trading/)
    - [application/](../src/trading/application/)
      - [__init__.py](../src/trading/application/__init__.py)
    - [domain/](../src/trading/domain/)
      - [__init__.py](../src/trading/domain/__init__.py)
    - [infrastructure/](../src/trading/infrastructure/)
      - [__init__.py](../src/trading/infrastructure/__init__.py)
    - [presentation/](../src/trading/presentation/)
      - [__init__.py](../src/trading/presentation/__init__.py)
    - [__init__.py](../src/trading/__init__.py)
  - [users/](../src/users/)
    - [application/](../src/users/application/)
      - [__init__.py](../src/users/application/__init__.py)
    - [domain/](../src/users/domain/)
      - [__init__.py](../src/users/domain/__init__.py)
    - [infrastructure/](../src/users/infrastructure/)
      - [__init__.py](../src/users/infrastructure/__init__.py)
    - [presentation/](../src/users/presentation/)
      - [__init__.py](../src/users/presentation/__init__.py)
    - [__init__.py](../src/users/__init__.py)
  - [wallet/](../src/wallet/)
    - [application/](../src/wallet/application/)
      - [__init__.py](../src/wallet/application/__init__.py)
    - [domain/](../src/wallet/domain/)
      - [__init__.py](../src/wallet/domain/__init__.py)
    - [infrastructure/](../src/wallet/infrastructure/)
      - [__init__.py](../src/wallet/infrastructure/__init__.py)
    - [presentation/](../src/wallet/presentation/)
      - [__init__.py](../src/wallet/presentation/__init__.py)
    - [__init__.py](../src/wallet/__init__.py)
  - [database.py](../src/database.py)
  - [main.py](../src/main.py)
- [tests/](../tests/)
  - [.gitkeep](../tests/.gitkeep)
- [.gitignore](../.gitignore)
- [.python-version](../.python-version)
- [pyproject.toml](../pyproject.toml)
- [README.md](../README.md)
- [uv.lock](../uv.lock)

## 도메인별 용도

| 폴더 | 역할 |
| --- | --- |
| [users](../src/users/) | 회원 정보와 회원 상태 관리 |
| [auth](../src/auth/) | 로그인·로그아웃·JWT 발급·검증·폐기 |
| [inventory](../src/inventory/) | 아이템 정의·보유 아이템·소유권·판매 예약 |
| [listing](../src/listing/) | 매물 등록·조회·검색·취소·판매 상태 관리 |
| [wallet](../src/wallet/) | 게임 재화 지갑·잔액 관리 |
| [trading](../src/trading/) | 구매 흐름 조율·거래 기록·거래 내역 |

모든 도메인은 현재 폴더 골조만 갖추고 있으며 기능은 **구현 예정**입니다. 각 도메인 루트와 계층의 빈 `__init__.py`는 Python 패키지 표시용이며, 기능 구현을 포함하지 않습니다. 개별 파일 링크는 위 전체 구조에 있습니다.

## 계층별 용도

아래 링크는 users 도메인을 예시로 하며, 6개 도메인에 같은 구조를 적용합니다.

| 폴더 | 역할 |
| --- | --- |
| [presentation](../src/users/presentation/) | API 요청·응답 검증, 라우터, HTTP 예외 변환 |
| [application](../src/users/application/) | 유스케이스 실행 순서와 트랜잭션 조율 |
| [domain](../src/users/domain/) | 순수 Python 도메인 객체·값 객체·핵심 검증·상태 전이 |
| [infrastructure](../src/users/infrastructure/) | ORM 모델·저장소 구현·DB 접근·도메인 객체 변환 |

각 계층의 기능은 **구현 예정**입니다.

## 공통 파일과 폴더

| 항목 | 용도 및 현재 상태 |
| --- | --- |
| [src/main.py](../src/main.py) | FastAPI 앱 진입점. 현재 앱과 `/health` 엔드포인트가 존재합니다. 라우터·미들웨어·lifespan 조립은 구현 예정입니다. |
| [src/database.py](../src/database.py) | 비동기 DB 엔진·세션·공통 Base·get_db 설정 위치. 현재 안내 주석만 있으며 구현 예정입니다. |
| [src/templates/](../src/templates/) | Jinja2 HTML 화면. 현재 `.gitkeep`만 있으며 구현 예정입니다. |
| [src/static/](../src/static/) | CSS·이미지·JavaScript 등 정적 파일. 현재 `.gitkeep`만 있으며 구현 예정입니다. |
| [tests/](../tests/) | 테스트 코드. 현재 `.gitkeep`만 있으며 구현 예정입니다. |
| [docs/](./) | 설계와 협업 문서. 현재 이 구조 안내 문서를 포함합니다. |
| [pyproject.toml](../pyproject.toml) | 프로젝트 정보·Python 요구 버전·의존성 설정. 기존 설정을 유지합니다. |
| [uv.lock](../uv.lock) | 의존성 잠금 파일. 기존 파일을 유지합니다. |
| [.python-version](../.python-version) | 사용할 Python 버전 지정. 기존 파일을 유지합니다. |
| [.gitignore](../.gitignore) | Git 추적 제외 규칙. 기존 규칙을 유지합니다. |
| [README.md](../README.md) | 프로젝트 안내와 구조 문서 진입 링크. |

빈 `.gitkeep`은 폴더를 Git으로 공유하기 위한 표시 파일입니다. 실행 코드는 포함하지 않습니다.

## 의존성과 협업 규칙

- presentation은 application과 domain을 사용합니다.
- application은 domain과 infrastructure를 사용하여 처리 흐름을 조율합니다.
- domain은 다른 계층이나 FastAPI·SQLAlchemy 등 외부 라이브러리에 의존하지 않습니다.
- infrastructure는 필요한 계약을 구현하고 ORM 모델과 도메인 객체를 변환합니다.
- 계층 간 순환 참조를 만들지 않습니다.
- 각 담당자는 자기 도메인 내부를 관리하고, 공통 파일 변경은 팀과 협의합니다.
- 다른 도메인의 내부 데이터를 직접 변경하지 않고 합의된 기능으로 협업합니다.
- 이번 작업은 폴더 골조 생성이며 기능 구현 완료를 의미하지 않습니다.

<p align="center">
  <img src="docs/readme/banner.svg" alt="Catch&amp;Bid, 낚시로 얻은 아이템을 경매장에서 거래하는 게임 데모" width="100%">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&amp;logo=python&amp;logoColor=white" alt="Python 3.13">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&amp;logo=fastapi&amp;logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/SQLAlchemy-async-D71F00?style=flat-square" alt="SQLAlchemy async">
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&amp;logo=postgresql&amp;logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Jinja2-B41717?style=flat-square&amp;logo=jinja&amp;logoColor=white" alt="Jinja2">
</p>

<p align="center">
  <b>백엔드 4계층 구조를 직접 만들어 보며 게임 데모를 구현한 팀 프로젝트</b><br>
  <i>낚시 아이템을 경매장에서 거래하는 주제의 게임을 다섯 개의 도메인과 웹 화면으로 구현</i>
</p>

<p align="center">
  <a href="#팀원과-역할-분담">팀 소개</a> / <a href="#협업-과정">협업 과정</a> / <a href="#프로젝트-구조">프로젝트 구조</a> / <a href="#화면-미리보기">화면 미리보기</a> / <a href="#실행-방법">실행 방법</a>
</p>

## 프로젝트 소개

Catch&Bid는 _"낚시로 얻은 아이템을 경매장에서 골드로 거래하는 게임"_ 컨셉으로 백엔드 4계층 (presentation / application / domain / infrastructure) 구조를 공부하기 위해 만든 학습용 팀 프로젝트입니다. FastAPI와 PostgreSQL로 만들었고, JSON API와 서버가 직접 그리는 웹 화면(Jinja2)을 같은 앱에서 함께 제공합니다. 기능별 도메인을 나누어 팀원이 각각 맡았고, 도메인끼리는 서로의 내부를 직접 부르지 않고 계약(Protocol)과 어댑터로만 연결합니다.

| 구성   | 내용                                                                         |
| ------ | ---------------------------------------------------------------------------- |
| 도메인 | auth (인증), users (회원), inventory (아이템), auction (경매), wallet (지갑) |
| 구조   | 도메인마다 presentation / application / domain / infrastructure 4계층        |
| 화면   | 서버 렌더링 HTML + JS·CSS                                                    |
| 협업   | Git, GitHub, Notion, Slack                                                   |

## 팀원과 역할 분담

<table>
  <tr>
    <td align="center"><a href="https://github.com/bsis09872-ux"><img src="https://github.com/bsis09872-ux.png?size=120" width="80" alt="bsis09872-ux GitHub 프로필"><br><b>배서인(journey)</b></a><br>경매</td>
    <td align="center"><a href="https://github.com/Cocode96"><img src="https://github.com/Cocode96.png?size=120" width="80" alt="Cocode96 GitHub 프로필"><br><b>양석호(coco)</b></a><br>인증 · 회원</td>
    <td align="center"><a href="https://github.com/uogji-lee"><img src="https://github.com/uogji-lee.png?size=120" width="80" alt="uogji-lee GitHub 프로필"><br><b>이연지(surl)</b></a><br>게임 클라이언트</td>
    <td align="center"><a href="https://github.com/ilmae-322"><img src="https://github.com/ilmae-322.png?size=120" width="80" alt="ilmae-322 GitHub 프로필"><br><b>김선규(ilmae)</b></a><br>지갑</td>
    <td align="center"><a href="https://github.com/eeseuju"><img src="https://github.com/eeseuju.png?size=120" width="80" alt="eeseuju GitHub 프로필"><br><b>이승주(bongo)</b></a><br>인벤토리</td>
  </tr>
</table>

| 이름   | GitHub                                          | 주요 담당                                       | 구현             |
| ------ | ----------------------------------------------- | ----------------------------------------------- | ---------------- |
| 배서인 | [bsis09872-ux](https://github.com/bsis09872-ux) | 경매(매물·입찰·마감 정산·거래)                  | (링크 연결 예정) |
| 양석호 | [Cocode96](https://github.com/Cocode96)         | 인증, 회원, 관리자 화면 연동과 조립             | (링크 연결 예정) |
| 이연지 | [uogji-lee](https://github.com/uogji-lee)       | 게임 클라이언트(게임 월드 맵·타일, 아이템 그림) | (링크 연결 예정) |
| 김선규 | [ilmae-322](https://github.com/ilmae-322)       | 지갑(잔액·정산)                                 | (링크 연결 예정) |
| 이승주 | [eeseuju](https://github.com/eeseuju)           | 아이템·인벤토리, 가방·경매 화면                 | (링크 연결 예정) |

## 협업 과정

도메인별로 작업 브랜치를 나누고, 담당 변경을 Pull Request로 올려 리뷰를 거쳐 `main`에 합쳤습니다.  
브랜치 이름은 `feature/닉네임/작업명` 형태로 구분했습니다.

```text
담당 기능 구현 → 작업 브랜치에 커밋 → push → Pull Request → 리뷰 → main에 병합
```

- 여러 도메인이 만나는 곳(경매가 인벤토리·지갑·회원을 부르는 부분)은 소비하는 쪽이 계약을 정하고, 제공하는 쪽이 어댑터로 맞췄습니다.
- 도메인 사이의 import 규칙은 검증 스크립트(`scripts/verify-domain-boundaries.py`)로 확인합니다.

## 프로젝트 구조

기능별 도메인 내부에 presentation, application, domain, infrastructure의 4계층을 구성합니다.

```text
AX_game_BE_api/
├─ src/
│  ├─ auth/ users/ inventory/ auction/ wallet/   # 도메인 (각각 4계층)
│  ├─ shared/                                     # 공통 예외, 로그, 아이템 이미지
│  ├─ templates/                                  # Jinja2 화면
│  ├─ static/                                     # JS, CSS, 이미지, 폰트
│  ├─ main.py                                     # 라우터 등록, 앱 시작·종료
│  └─ database.py                                 # DB 연결
├─ scripts/                                       # 검증·마이그레이션 스크립트
├─ docs/                                          # 구조 안내와 화면 캡처
├─ .env.example                                   # 환경변수 예시
└─ pyproject.toml
```

도메인끼리는 이렇게 연결됩니다.

```mermaid
flowchart LR
    C["클라이언트<br/>웹 화면 · 외부 API"] --> A["auction<br/>매물 · 입찰 · 마감 정산"]
    C --> I["inventory<br/>아이템 · 소유 이력"]
    C --> U["auth · users<br/>로그인 · 회원"]
    C --> W["wallet<br/>잔액 · 정산"]
    A -.->|"계약 + 어댑터"| I
    A -.->|"계약 + 어댑터"| W
    A -.->|"계약 + 어댑터"| U
    I -.->|"토큰·역할 확인"| U
    A & I & U & W --> DB[("PostgreSQL")]
```

_※ 폴더별 역할과 협업 규칙은 [프로젝트 구조 안내](docs/project-structure.md)를, 도메인별 설계와 구현 현황은 각 도메인의 README를 참고해주세요._

## 화면 미리보기

<!-- 캡처 파일을 docs/readme/ 에 넣은 뒤, 아래 칸의 "(캡처 추가 예정)"을 <a href="docs/readme/파일명.png"><img src="docs/readme/파일명.png" alt="설명" width="100%"></a> 로 바꾸세요. -->
<table>
  <tr>
    <td width="33%"><br><br><br>(캡처 추가 예정)<br><br><br><b>로그인 · 회원가입</b><br><code>/login · /register</code></td>
    <td width="33%"><br><br><br>(캡처 추가 예정)<br><br><br><b>내 정보</b><br><code>/me</code></td>
    <td width="33%"><br><br><br>(캡처 추가 예정)<br><br><br><b>내 가방</b><br><code>/inventory</code></td>
  </tr>
  <tr>
    <td width="33%"><br><br><br>(캡처 추가 예정)<br><br><br><b>아이템 상세 · 도감</b><br><code>/inventory/{id} · /item-catalogs</code></td>
    <td width="33%"><br><br><br>(캡처 추가 예정)<br><br><br><b>경매장 목록</b><br><code>/auctions</code></td>
    <td width="33%"><br><br><br>(캡처 추가 예정)<br><br><br><b>경매 상세 (입찰)</b><br><code>/auctions/{id}</code></td>
  </tr>
  <tr>
    <td width="33%"><br><br><br>(캡처 추가 예정)<br><br><br><b>경매 등록</b><br><code>/auctions/new</code></td>
    <td width="33%"><br><br><br>(캡처 추가 예정)<br><br><br><b>내 거래</b><br><code>/auctions/trades</code></td>
    <td width="33%"><br><br><br>(캡처 추가 예정)<br><br><br><b>지갑</b><br><code>/wallet</code></td>
  </tr>
  <tr>
    <td width="33%"><br><br><br>(캡처 추가 예정)<br><br><br><b>관리자 / 카탈로그</b><br><code>/admin/catalogs</code></td>
    <td width="33%"><br><br><br>(캡처 추가 예정)<br><br><br><b>관리자 / 경매 · 거래</b><br><code>/admin/auctions</code></td>
    <td width="33%"><br><br><br>(캡처 추가 예정)<br><br><br><b>관리자 / 회원</b><br><code>/admin/members</code></td>
  </tr>
</table>

## 실행 방법

### 준비

Python 3.13과 [uv](https://docs.astral.sh/uv/)가 필요합니다. PostgreSQL을 준비하고 `catchbid` 같은 빈 데이터베이스를 만듭니다. Docker를 쓴다면 예를 들어 다음과 같이 띄웁니다.

```bash
docker run --name catchbid-pg -e POSTGRES_PASSWORD=비밀번호 -e POSTGRES_DB=ax_game -p 5432:5432 -d postgres
```

- `.env.example`을 `.env.local`로 복사하고 아래 두 값만 채우면 됩니다. 나머지 설정은 기본값이 있습니다.
  - `DATABASE_URL`: `postgresql+asyncpg://사용자:비밀번호@127.0.0.1:5432/ax_game`
  - `JWT_SECRET_KEY`: 토큰 서명용 무작위 값 (32바이트 이상)

### 실행

프로젝트 루트에서 실행합니다. `--app-dir src`는 `src`를 모듈 검색 경로에 추가합니다. 처음 켤 때 테이블이 자동으로 만들어집니다.

```bash
uv sync
uv run uvicorn main:app --app-dir src --reload
```

이미 `src` 폴더에 있다면 다음 명령으로 실행합니다.

```bash
uv run uvicorn main:app --reload
```

서버를 켜면 브라우저에서 확인할 수 있습니다.

| 주소                              | 내용              |
| --------------------------------- | ----------------- |
| `http://127.0.0.1:8000/login`     | 로그인과 회원가입 |
| `http://127.0.0.1:8000/v1/play`   | 낚시 클라이언트   |
| `http://127.0.0.1:8000/inventory` | 내 가방           |
| `http://127.0.0.1:8000/auctions`  | 경매장            |
| `http://127.0.0.1:8000/docs`      | API 문서(Swagger) |
| `http://127.0.0.1:8000/health`    | 상태 확인         |

기본 아이템 카탈로그가 필요하면 앱을 한 번 켜서 테이블이 만들어진 뒤 저장소 루트에서 시드를 실행합니다.

```bash
PYTHONPATH=src uv run python -m inventory.infrastructure.seed
```

낚시 화면과 서버 연결은 [클라이언트 README](src/client/README.md), CORS와 요청 로그 설정은 [공통 미들웨어 문서](src/shared/core/README.md)를 확인합니다.

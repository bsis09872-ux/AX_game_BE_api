# 회원과 인증 API

회원가입 저장, 로그인 JWT 발급, 현재 토큰 로그아웃, 내 정보 조회를 제공한다. 지갑 생성은 연결하지 않는다. 회원이 생성돼도 지갑은 없을 수 있다.

## 실행

Python 3.13 이상과 PostgreSQL을 사용한다. 저장소 루트에서 `uv sync` 후 `.env.example`을 `.env`로 복사한다. `DATABASE_URL`을 프로젝트 DB에 맞게 지정하고 아래 명령으로 생성한 값을 `JWT_SECRET_KEY`에 넣는다. `.env`는 Git에서 제외된다.

```powershell
uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
uv run uvicorn main:app --app-dir src --reload
```

서버는 시작할 때 JWT 설정을 검증하고 `users`, `revoked_tokens` 테이블을 준비한다. 기존 테이블의 컬럼이나 제약을 변경하는 마이그레이션은 수행하지 않는다. Swagger는 `/docs`, 상태 확인은 `/health`다.

| 설정 | 내용 |
| --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://` 연결 문자열 |
| `JWT_SECRET_KEY` | 필수. 32바이트 이상 무작위 비밀키 |
| `JWT_TTL_SECONDS` | 기본 1800초. 허용 범위 60~86400초 |

토큰은 발급 시각 기준으로 만료된다. 요청할 때마다 만료 시각이 연장되는 비활동 만료 방식은 아니다. 설정 변경은 서버 재시작 후 적용된다.

## HTTP 계약

| 요청 | 입력 | 성공 응답 |
| --- | --- | --- |
| `POST /v1/auth/register` | JSON `login_id`, `display_name`, `password` | 201, `id`, `login_id`, `created_at` |
| `POST /v1/auth/token` | 폼 `username`, `password` | 200, `access_token`, `token_type`, `expires_in` |
| `POST /v1/auth/logout` | Bearer 토큰 | 204, 본문 없음 |
| `GET /v1/users/me` | Bearer 토큰 | 200, `id`, `login_id`, `display_name`, `role`, `created_at` |

로그인 폼의 `username`은 `login_id`다. `Content-Type: application/x-www-form-urlencoded`를 사용한다. Swagger의 Authorize에서도 같은 필드를 입력한다. 인증이 필요한 요청에는 `Authorization: Bearer <access_token>`을 전달한다.

가입 예시:

```json
{"login_id":"coco","display_name":"코코","password":"example-password"}
```

로그인 ID는 소문자, 숫자, 밑줄 4~50자다. 표시 이름은 공백이 아닌 문자를 포함한 1~50자로 제한해 거래 스냅샷의 이름 길이와 맞춘다. 비밀번호는 현재 1~1024자를 허용하며 별도 복잡도 정책은 적용하지 않는다. 역할 등 선언하지 않은 가입 필드는 422로 거절한다.

회원 ID는 응답에서 10진 문자열로 변환하고 시각은 UTC ISO 8601로 반환한다. 비밀번호 해시와 내부 상태는 응답에서 제외한다.

| 오류 | 상태 | 처리 |
| --- | --- | --- |
| `LOGIN_ID_ALREADY_EXISTS` | 409 | 사전 중복 조회 또는 DB 유일 제약 위반 |
| `INVALID_CREDENTIALS` | 401 | 없는 계정, 틀린 비밀번호, 탈퇴 계정의 로그인 |
| `AUTHENTICATION_REQUIRED` | 401 | Bearer 토큰 없음 |
| `INVALID_TOKEN` | 401 | 서명/필수 claim 오류, 만료, 폐기, 회원 없음/탈퇴 |
| 요청 필드 검증 오류 | 422 | `detail` 배열에 `type`, `loc`, `msg`만 반환 |
| `INTERNAL_SERVER_ERROR` | 500 | 저장 실패 또는 예상하지 못한 내부 오류 |

업무/인증 오류는 `{"detail":{"code":"...","message":"..."}}` 형식이다. 인증 오류에는 `WWW-Authenticate: Bearer`를 포함한다. 검증 오류에 입력 원문을 반환하지 않는다.

## 구조와 연결

```text
presentation/router.py
  → dependencies.py: 요청의 세션과 토큰을 주입
  → wiring.py: 같은 세션으로 구현체를 조립
  → AuthService: 계약으로 해싱/회원/토큰/트랜잭션 호출
      → UserCreatorAdapter, UserReaderAdapter → UserService → 회원 저장소
      → PasslibPasswordHasher → bcrypt_sha256, 별도 스레드
      → JwtTokenCodec → HS256 서명과 필수 claim 검증
      → SqlAlchemyRevokedTokenRepository → 폐기한 jti 저장
```

`auth/application/contracts.py`는 인증에서 필요한 계약을 소유한다. `auth/infrastructure/user_reader.py`와 `user_creator.py`만 users의 실제 서비스를 연결한다. `users/application`과 `users/domain`은 auth 구현을 import하지 않는다. `users/presentation/router.py`는 HTTP 인증 경계이므로 auth의 인증 의존성을 사용한다.

다른 API의 인증 확인은 `Depends(get_current_token)`을 사용한다. 검증된 `claims.user_id`로 본인 데이터를 조회한다. 클라이언트가 보낸 회원 ID를 본인 인증의 근거로 사용하지 않는다.

```python
from fastapi import Depends
from auth.application.contracts import TokenClaims
from auth.presentation.dependencies import get_current_token

async def endpoint(claims: TokenClaims = Depends(get_current_token)):
    return {"user_id": str(claims.user_id)}
```

`register_user`와 `logout`은 반환 전에 commit한다. 실패 시 `database.get_db`가 rollback하고 세션을 닫는다. HTTP 밖에서 서비스를 호출할 때는 호출자가 세션 수명과 rollback을 관리해야 한다. 저장소는 자체적으로 commit하지 않는다.

로그아웃은 현재 JWT만 폐기한다. 같은 유효 토큰으로 반복 호출해도 204이며 다른 로그인 토큰은 유지된다. 이미 만료된 토큰은 401이다. 진행 중인 요청을 취소하지는 않으며, 폐기가 commit된 이후 인증 검사에서 차단한다.

## 검증

단위 테스트:

```powershell
uv run python -m unittest discover -s tests -p test_auth_unit.py -v
```

Docker가 실행 중이고 `postgres:18` 이미지가 준비돼 있으면 아래 명령으로 임시 DB에서 전체 테스트를 실행한다. 실행기는 기존 DB에 접근하지 않으며 종료 시 생성한 컨테이너를 제거한다.

```powershell
uv run python tests/run_auth_integration.py
```

가입 후 별도 세션 조회, 비밀번호 검증, 내 정보의 공개 필드, JWT 변조/만료/claim 오류, 동시 중복 가입 201/409, 동시 로그아웃, 폐기 토큰 차단, 탈퇴 계정 거절, 가입/로그아웃 commit 실패 rollback, OpenAPI 등록을 확인한다.

## 현재 범위

지갑 생성, 토큰 갱신, 회원 수정/탈퇴 API, 관리자 권한 API와 요청 횟수 제한은 포함하지 않는다. 만료된 `revoked_tokens` 행의 정리 작업도 아직 없다. 다른 프로젝트에서 재사용하려면 `src/auth`, `src/users`뿐 아니라 `database.py`, 공통 예외, `main.py`의 등록 부분과 환경 설정을 함께 연결해야 한다. 독립 설치형 SDK는 아니다.

JWT 검증은 [PyJWT 공식 문서](https://pyjwt.readthedocs.io/en/stable/api.html), 폼 로그인과 Bearer 전달은 [FastAPI 공식 문서](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)를 기준으로 한다.

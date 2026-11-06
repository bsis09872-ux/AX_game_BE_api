# 회원 인증 로컬 실행과 검증

팀원마다 자신의 PostgreSQL과 백엔드 서버를 실행한다. 다른 팀원의 DB 주소, 비밀번호나 JWT 비밀키를 공유할 필요는 없다. 이 문서는 PR #13의 실행 방법이며, 구현 과제나 자동 테스트 코드를 포함하지 않는다.

## 1. 코드와 개인 DB 준비

PR 병합 전에는 다음 브랜치에서 확인한다. 작업 중인 파일이 있으면 먼저 보존한다.

```powershell
git fetch origin
git switch feature/coco/users-auth-web
uv sync
```

PR #12와 #13이 main에 병합된 이후에는 최신 main에서 실행해도 된다. Python 요구 버전은 3.13 이상이다.

이미 개인 PostgreSQL과 `ax_game` DB가 있으면 그대로 사용한다. 새 DB만 필요한 경우 PostgreSQL 관리 도구에서 `postgres` DB에 연결한 뒤 아래 SQL을 별도로 실행한다. 같은 이름의 DB가 이미 있으면 생성하지 않는다.

```sql
CREATE DATABASE ax_game;
```

PostgreSQL 자체가 없고 Docker를 쓰는 경우의 예시다. `CHANGE_ME`는 자신만의 개발용 비밀번호로 바꾼다.

```powershell
docker run --name ax-game-postgres --detach --publish 127.0.0.1:5432:5432 --env POSTGRES_USER=postgres --env POSTGRES_PASSWORD=CHANGE_ME --env POSTGRES_DB=ax_game --volume ax-game-pgdata:/var/lib/postgresql postgres:18
```

이 명령은 새 컨테이너를 만들 때 한 번 사용한다. 이미 같은 컨테이너가 있으면 `docker start ax-game-postgres`로 시작한다. 5432가 사용 중이면 기존 서비스를 임의로 삭제하지 않고 `5433:5432`처럼 개인 포트를 선택한 뒤 아래 연결 URL도 맞춘다. DB 이름만 연결 도구에 입력한다고 실제 DB가 생성되지는 않는다.

## 2. .env.local 설정

기존 `.env.local`이 없을 때만 저장소 루트에서 복사한다.

```powershell
Copy-Item .env.example .env.local
uv run python -c "import secrets; print(secrets.token_urlsafe(48))"
```

출력된 무작위 값을 자신의 `JWT_SECRET_KEY`에 넣는다. `.env.example`에 아직 없는 두 설정은 `.env.local`에 직접 추가할 수 있다.

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:CHANGE_ME@127.0.0.1:5432/ax_game
JWT_SECRET_KEY=여기에_각자_생성한_무작위_값
JWT_TTL_SECONDS=1800
REFRESH_TTL_SECONDS=604800
WEB_ORIGIN=http://127.0.0.1:8000
```

- `DATABASE_URL`: 자신이 만든 DB의 사용자, 비밀번호, 호스트 포트와 DB 이름을 사용한다. 비밀번호에 URL 예약 문자가 있으면 URL 인코딩한다.
- `JWT_SECRET_KEY`: 32바이트 이상의 무작위 값이다. 저장소나 PR에 올리지 않는다.
- `JWT_TTL_SECONDS`: Access token 수명, 60~86400초.
- `REFRESH_TTL_SECONDS`: 로그인 세션의 최종 수명, 30~2592000초. 계속 사용하거나 갱신해도 이 세션의 종료 시각은 연장되지 않는다.
- `WEB_ORIGIN`: 실제 브라우저 접속 주소와 포트까지 일치해야 한다. 위 설정이면 `localhost` 대신 `127.0.0.1`로 접속한다.

프로세스에 이미 지정된 환경변수가 파일보다 우선하며, 파일은 `.env.local`, `.env` 순으로 읽는다. 설정을 변경하면 서버를 재시작하고 새로 로그인한다. 기존 로그인 세션에는 생성 당시 만료 시각이 남는다.

## 3. 서버 실행

```powershell
uv run uvicorn main:app --app-dir src --reload --host 127.0.0.1 --port 8000
```

| 주소 | 확인할 내용 |
| --- | --- |
| `http://127.0.0.1:8000/health` | `{"status":"ok"}` |
| `http://127.0.0.1:8000/register` | 회원가입 화면 |
| `http://127.0.0.1:8000/login` | 로그인 화면 |
| `http://127.0.0.1:8000/me` | 로그인한 본인 정보, 미인증이면 로그인으로 이동 |
| `http://127.0.0.1:8000/docs` | API 문서 |

시작 시 없는 테이블을 생성한다. 기존 테이블의 컬럼이나 제약을 수정하는 마이그레이션 기능은 아니다. 실행 성공은 위 주소의 응답과 서버 시작 로그로 확인한다.

## 4. 브라우저 검증 순서

검증용 ID와 비밀번호는 각자 새로 정한다. 아래 스크린샷의 회원은 별도 임시 DB에 만든 가상 회원이다.

| 순서 | 수행 | 예상 결과 |
| --- | --- | --- |
| 1 | 로그아웃 상태에서 `/me` 접속 | `/login`으로 이동 |
| 2 | `/register`에서 새 ID, 표시 이름, 비밀번호로 가입 | 로그인 화면으로 이동하며 가입 완료 안내 |
| 3 | 같은 ID로 다시 가입 | 중복 안내, 비밀번호 입력은 비워짐 |
| 4 | 다른 ID와 표시 이름 공백 두 칸으로 가입 시도 | 서버의 표시 이름 오류 안내, 회원 생성 안 됨 |
| 5 | 기존 ID와 틀린 비밀번호로 로그인 | 계정 또는 비밀번호 오류 안내 |
| 6 | 정상 비밀번호로 로그인 | `/me`에 본인 ID, 표시 이름, 역할, 가입 시각 표시 |
| 7 | `/me` 새로고침 | 유효한 세션이면 본인 정보 유지 |
| 8 | 로그아웃 클릭 후 `/me` 재접속 | 로그인 화면, 이전 세션으로 접근 불가 |

로그인 ID는 소문자/숫자/밑줄 4~50자, 표시 이름은 공백 아닌 문자를 포함한 2~50자다. 비밀번호는 현재 1~1024자다. HTML 입력 제한은 사용자를 돕는 기능이며 최종 검증은 서버에서 수행한다.

## 5. 만료와 자동 재발급 검증

### 30초 후 자동으로 로그인 화면 이동

```dotenv
JWT_TTL_SECONDS=1800
REFRESH_TTL_SECONDS=30
```

서버를 재시작하고 새로 로그인한다. `/me`를 전면에 둔 채 새로고침이나 클릭 없이 기다린다. 약 30초 후 `/login?expired=1`로 이동하며 만료 안내가 표시된다. Access token의 30분 수명이 남아 있어도 로그인 세션이 끝나면 접근할 수 없다. 백그라운드나 절전 상태에서 브라우저가 타이머를 중단하면 화면 복귀 시 만료를 확인한다.

### Access token 자동 갱신과 고정 세션 종료

```dotenv
JWT_TTL_SECONDS=60
REFRESH_TTL_SECONDS=90
```

서버를 재시작하고 새로 로그인한다. 개발자 도구 Network에서 `/session`과 `/session/refresh` 요청을 확인한다. Access token 수명이 30초 이하가 되면 갱신 요청이 발생하고 `/me`를 유지한다. 갱신해도 로그인 시점부터 약 90초 후에는 로그인 화면으로 이동한다. 정상적인 동작이다.

검증 뒤에는 자신의 기본 설정으로 되돌리고 재시작한다. 위 짧은 수명은 검증용이다. API 클라이언트는 `/v1/auth/refresh`를 호출하고 매번 새로 받은 refresh token으로 교체해야 한다. 이미 사용한 refresh token을 재사용하면 해당 로그인 세션이 폐기된다.

## 6. DB에서 확인할 내용

DBeaver 등에서 자신의 `ax_game` DB에 연결한다. 아래 `YOUR_TEST_LOGIN_ID`를 자신의 검증용 ID로 바꾼다. 비밀번호 해시와 토큰 원문/해시는 조회 결과나 공유 스크린샷에 포함하지 않는다.

```sql
SELECT id, login_id, display_name, role, created_at, deleted_at
FROM users
WHERE login_id = 'YOUR_TEST_LOGIN_ID';

SELECT s.id, s.created_at, s.expires_at, s.revoked_at,
       count(r.token_hash) AS refresh_rows,
       count(r.used_at) AS used_refresh_rows
FROM auth_sessions s
JOIN users u ON u.id = s.user_id
LEFT JOIN refresh_tokens r ON r.session_id = s.id
WHERE u.login_id = 'YOUR_TEST_LOGIN_ID'
GROUP BY s.id
ORDER BY s.created_at DESC;

SELECT t.expires_at, t.revoked_at
FROM revoked_tokens t
JOIN users u ON u.id = t.user_id
WHERE u.login_id = 'YOUR_TEST_LOGIN_ID'
ORDER BY t.revoked_at DESC;
```

- 로그인하면 새 세션과 refresh 기록이 생성된다.
- 자동 재발급되면 같은 세션에서 refresh 기록 수와 사용된 기록 수가 증가한다. `expires_at`은 그대로다.
- 로그아웃한 세션은 `revoked_at`이 채워진다.
- 시간 만료만으로 `revoked_at`이 채워지는 것은 아니다. `expires_at`과 현재 시각을 비교해 만료를 판단한다.
- 만료된 행과 사용된 refresh 기록은 삭제하지 않는다. 화면 이동이 DB 행 삭제를 의미하지 않는다.

## 7. API 확인과 문제 구분

Swagger에서 회원가입 후 `/v1/auth/token`의 `username`에 로그인 ID를 넣어 토큰을 발급한다. Authorize에도 같은 ID와 비밀번호를 사용한다. 브라우저 화면 로그인과 Swagger의 Bearer 인증은 별도 흐름이다.

| 요청 | 예상 결과 |
| --- | --- |
| `POST /v1/auth/register` | 새 회원 201, 중복 409, 잘못된 입력 422 |
| `POST /v1/auth/token` | 정상 200, 잘못된 계정/비밀번호 401 |
| `GET /v1/users/me` | 유효한 Bearer token 200, 미인증/만료 401 |
| `POST /v1/auth/refresh` | 유효한 refresh token 200과 새 토큰 쌍 |
| `POST /v1/auth/logout` | 현재 로그인 세션 폐기, 204 |
| `POST /v1/auth/refresh/logout` | refresh token으로 세션 폐기, 204 |

인증 응답을 공유할 때 토큰이나 쿠키 값을 캡처하지 않는다. 반복된 refresh 재사용, 동시 요청과 rollback은 로컬 자동 테스트에서도 검증했으며 테스트 소스는 이번 PR에 포함하지 않았다.

| 증상 | 확인 |
| --- | --- |
| DB 접속 실패 | PostgreSQL 실행, 호스트 포트, 비밀번호, 실제 DB 생성 여부 |
| JWT 설정 오류로 시작 실패 | 비밀키 길이와 생성 여부, TTL 허용 범위 |
| 웹 POST 403 | 브라우저 주소와 WEB_ORIGIN 일치 여부 |
| 서버 포트 충돌 | 기존 서버 확인 후 다른 포트를 쓰면 WEB_ORIGIN도 변경 |
| 설정을 바꿨는데 기존 시간으로 만료 | 프로세스 환경변수 우선순위, 서버 재시작, 새 로그인 여부 |

## 8. 실제 화면

2026-11-06, PR 구현 커밋 `887127d`에서 별도 임시 PostgreSQL과 8013 포트 서버로 확인했다. 사용 중인 개인 DB와 8000 서버는 변경하지 않았다.

- Access token 60초 / 세션 90초: 정상 가입, 중복 409, 입력 오류 422, 로그인 오류 401, 내 정보, 새로고침, 로그아웃과 미인증 접근 차단을 확인했다. 아무 조작 없이 자동 갱신 2회를 거친 뒤 만료 화면으로 이동했다. DB의 해당 세션에 refresh 기록 3개, 사용된 기록 2개가 남았고 최종 만료 시각은 유지됐다.
- Access token 1800초 / 세션 30초: 새 임시 DB에서 별도로 로그인한 뒤 조작 없이 만료 화면으로 이동하는지 확인했다.
- 화면은 실제 브라우저에서 캡처했다. 서버 테스트 40개 및 가상 시계 테스트 9개와 별도로 수행한 검증이다.

### 회원가입
![회원가입 화면](screenshots/users-auth/01-register.jpg)

### 가입 완료
![가입 완료 후 로그인 안내](screenshots/users-auth/02-register-success.jpg)

### 로그인 실패
![잘못된 비밀번호 안내](screenshots/users-auth/03-login-error.jpg)

### 중복 회원가입
![중복 아이디 안내](screenshots/users-auth/04-register-duplicate.jpg)

### 표시 이름 검증
![공백 표시 이름 거절](screenshots/users-auth/05-register-validation.jpg)

### 본인 정보
![로그인 후 본인 정보](screenshots/users-auth/06-profile.jpg)

### 로그아웃
![로그아웃 후 로그인 화면](screenshots/users-auth/07-logout.jpg)

### 세션 만료
![조작 없이 만료 후 로그인 화면](screenshots/users-auth/08-session-expired.jpg)

### Access token 30분 / 세션 30초: 로그인 직후
![30초 세션 로그인 직후](screenshots/users-auth/09-short-session-profile.jpg)

### Access token 30분 / 세션 30초: 만료 후
![30초 세션 만료 후 로그인 화면](screenshots/users-auth/10-short-session-expired.jpg)

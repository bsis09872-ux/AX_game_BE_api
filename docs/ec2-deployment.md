# EC2 배포 준비와 검증 범위

2026-11-11 기준, 다른 팀원 AWS 계정에 접속하거나 배포하지 않았습니다. 로컬 Linux 컨테이너에서 Python 3.13.18, PostgreSQL 17, Nginx HTTPS 프록시와 Uvicorn 2 worker를 실행해 설치와 주요 연결을 확인했습니다. EC2의 AMI, CPU 아키텍처, 보안 그룹, 실제 인증서, DNS, DB 구성과 부하 수용량은 아직 검증하지 않았습니다.

## 권장 시작 구성

한 EC2에서 Nginx가 HTTPS를 받고, 앱은 `127.0.0.1:8000`에서 실행하는 구성을 기준으로 합니다. 클라이언트 파일도 같은 앱이 제공하므로 별도 프런트엔드 서버가 필요하지 않습니다. PostgreSQL은 EC2 내부 또는 별도 DB에 둘 수 있으며 위치는 운영 담당자가 결정해야 합니다.

처음에는 worker 1개로 시작하는 것을 권장합니다. 두 worker의 DB 공유와 WSS 연결은 확인했지만 접속자 부하 시험과 다중 스케줄러 운영 시험을 완료한 것은 아닙니다. 현재 앱은 worker마다 경매 마감 스케줄러를 실행합니다.

## 설정

| 환경변수 | 배포 시 값/의미 |
| --- | --- |
| `DATABASE_URL` | 준비한 PostgreSQL 주소. 모든 worker가 같은 DB 사용 |
| `JWT_SECRET_KEY` | 충분히 긴 무작위 비밀값. 모든 worker가 같은 값 사용 |
| `WEB_ORIGIN` | 브라우저가 접속할 `https://실제도메인` 또는 포트를 포함한 정확한 Origin. 끝에 `/` 없음 |
| `CORS_ALLOWED_ORIGINS` | 같은 사이트 배포면 생략 가능. 기본값은 `WEB_ORIGIN`. `*` 사용 불가 |
| `DEMO_FISHING_ENABLED` | 현재 기본 `true`. 보상 기능을 끄려면 명시적으로 `false` |
| `ITEM_IMAGE_DIR` | 배포 디렉터리 교체와 별개로 유지되는 업로드 이미지 경로 |

쿠키의 Secure 설정은 HTTPS `WEB_ORIGIN`에서 활성화됩니다. CORS 목록을 늘리는 것만으로 쿠키 쓰기/WS의 Origin 검사를 통과하지는 않습니다. 현재 화면과 API는 같은 Origin을 사용하는 구성을 전제로 합니다. `JWT_TTL_SECONDS`, `REFRESH_TTL_SECONDS`는 기존 Auth 설정을 유지하고 운영 세션 정책에 맞춰 결정합니다.

비밀값은 저장소에 올리지 않고 EC2의 제한된 환경 파일이나 운영 비밀 저장소에서 제공합니다. 기존 `.env.local`을 다른 계정의 서버에 그대로 복사하지 않습니다.

## 설치와 DB 준비

검토한 커밋을 clone/checkout한 후 Python 3.13과 uv를 준비하고 `uv sync --frozen --no-dev`를 실행합니다. Linux에서는 파일명 대소문자를 구분합니다. 현재 낚시 화면의 실제 리소스 로딩은 Linux 브라우저 QA에서 확인했습니다.

**기존 DB를 연결하기 전에 백업과 복원 절차를 확인해야 합니다.** 앱을 켜면 만료 경매 정산이 시작됩니다. 조회 목적이라고 기존 DB로 앱을 실행하지 않습니다. 이번 QA는 무작위 QA DB만 사용했으며 운영 데이터의 백업/복원은 수행하지 않았습니다.

아래 명령은 환경변수를 준비한 상태에서 스키마만 초기화하는 예시입니다. 앱의 lifespan을 실행하지 않아 경매 스케줄러를 시작하지 않습니다. worker 여러 개를 동시에 최초 실행해 테이블을 경쟁 생성하지 않도록 먼저 한 번 실행합니다.

```bash
PYTHONPATH=src uv run --frozen --no-dev python - <<'PY'
import asyncio
import main
from database import Base, engine
from users.infrastructure.schema import upgrade_member_controls

async def initialize():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await upgrade_member_controls(connection)
    await engine.dispose()

asyncio.run(initialize())
PY
```

`create_all`은 기존 테이블의 컬럼 변경까지 처리하지 않습니다. 이전 경매 DB에는 저장소의 `scripts/migrate-auction-admin-cancel.py` 적용 여부를 확인합니다. 투척 검증에는 새 `world_presences`, `fishing_attempts`, `fishing_cooldowns` 테이블이 필요합니다.

빈 개발/검증 DB에 기본 카탈로그가 필요할 때만 `PYTHONPATH=src uv run --frozen python -m inventory.infrastructure.seed`를 실행합니다. 시드는 서버 시작 시 자동 실행되지 않습니다. 기존 운영 데이터에 시드를 적용할지는 담당자가 따로 판단합니다.

앱 실행 예시:

```bash
uv run --frozen --no-dev uvicorn main:app --app-dir src \
  --host 127.0.0.1 --port 8000 --workers 1 \
  --proxy-headers --forwarded-allow-ips 127.0.0.1 --ws-max-size 2048
```

운영에서는 재시작을 관리할 서비스에 위 명령과 환경 파일을 등록합니다. 개발용 `--reload`는 사용하지 않습니다. 프록시가 다른 호스트/컨테이너에 있다면 실제 신뢰할 프록시 주소와 앱 바인딩 주소를 함께 조정해야 합니다. 모든 외부 요청의 전달 헤더를 신뢰하도록 바꾸지 않습니다.

## HTTPS와 WebSocket 프록시

Nginx의 `http` 블록 안에 다음과 같이 구성합니다. 인증서 경로와 도메인은 운영 값으로 교체합니다. `Upgrade`와 `Connection` 헤더를 명시적으로 전달해야 WSS 연결이 가능합니다. [Nginx 공식 WebSocket 문서](https://nginx.org/en/docs/http/websocket.html)

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}

server {
    listen 443 ssl;
    server_name game.example.com;
    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_read_timeout 75s;
    }
}
```

`/v1/play`, `/v1/ws/world`, `/static`을 포함한 모든 경로를 같은 Origin으로 전달합니다. 브라우저는 HTTPS 페이지에서 자동으로 `wss://`를 선택합니다. 자체 서명 인증서와 인증서 검증 생략은 로컬 QA에서만 사용했습니다.

EC2 보안 그룹은 HTTPS 인바운드를 허용하고 앱의 8000과 DB의 5432를 인터넷에 직접 개방하지 않는 구성을 권장합니다. SSH가 필요하면 관리자의 허용 주소로 제한합니다. HTTP 리다이렉트/인증서 발급용 포트는 선택한 인증서 운영 방식에 따라 결정합니다. 보안 그룹은 인바운드와 아웃바운드 트래픽을 제어합니다. [AWS 공식 설명](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-security-groups.html)

## 확인한 결과와 남은 운영 검증

| 범위 | 이번 확인 결과 |
| --- | --- |
| Linux 새 환경 설치 | 잠금 파일 기준 설치와 앱 시작 성공 |
| HTTPS 인증 | 회원가입/로그인, Secure/HttpOnly 쿠키, `/v1/play` 조회 성공 |
| 미들웨어 | CORS 허용 응답과 `X-Process-Time` 확인, 별도 자동 테스트 12개 통과 |
| Linux 실제 화면 | 오프닝, 첫 프레임과 리소스 로딩, 브라우저 WSS 연결 성공 |
| Nginx + 2 worker | 두 계정 접속/위치 공유, 로그아웃 세션 폐기 후 WS 종료 성공 |
| 격리 DB 전체 QA | 투척 검증, 공유 쿨다운, 응답 유실/재시작 후 중복 지급 방지, 관리자 회귀 검증 통과 |
| 실제 EC2 | 접속/배포하지 않음. 인증서, 보안 그룹, DNS와 인스턴스 성능 미검증 |
| 운영 데이터 | 기존 DB 변경 없음. 백업/복원과 데이터 증가에 따른 보관 정책 미검증 |

World는 플레이어마다 주기적으로 DB를 조회하는 구조입니다. 정원 30명은 성능 보장이 아니므로 worker를 늘리기 전에 실제 EC2에서 CPU, DB 연결/쿼리 지연과 응답 시간을 측정해야 합니다. 성공한 투척 기록은 재확인에 사용하므로 정리 정책을 정하기 전 임의로 삭제하면 안 됩니다.

배포 전 기존 커밋과 설정을 기록하고 DB/이미지를 백업합니다. 배포 후 두 계정의 로그인, 낚시 지급, 경매와 관리자 조회를 확인합니다. 문제가 있으면 이전 앱 커밋으로 복구하되 새 테이블을 즉시 삭제하지 않습니다. 실제 운영 복구 절차와 소요 시간은 별도 검증이 필요합니다.

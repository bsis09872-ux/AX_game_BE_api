"""기존 DB에 접근하지 않고 임시 PostgreSQL 컨테이너에서 통합 테스트를 실행한다."""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from uuid import uuid4


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    name = f"ax-auth-test-{uuid4().hex[:12]}"
    password = secrets.token_urlsafe(24)
    started = False
    try:
        subprocess.run([
            "docker", "run", "--rm", "--detach", "--pull=never", "--name", name,
            "--tmpfs", "/var/lib/postgresql:rw", "--publish", "127.0.0.1::5432",
            "--env", f"POSTGRES_PASSWORD={password}", "--env", "POSTGRES_DB=auth_test",
            "postgres:18",
        ], check=True, capture_output=True)
        started = True
        for _ in range(100):
            ready = subprocess.run(
                ["docker", "exec", name, "pg_isready", "-U", "postgres", "-d", "auth_test"],
                capture_output=True,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("임시 PostgreSQL 준비 시간 초과")
        mapping = subprocess.check_output(
            ["docker", "port", name, "5432/tcp"], text=True
        ).strip()
        port = mapping.rsplit(":", 1)[1]
        env = os.environ.copy()
        env["AUTH_TEST_DATABASE_URL"] = f"postgresql+asyncpg://postgres:{password}@127.0.0.1:{port}/auth_test"
        env["DATABASE_URL"] = env["AUTH_TEST_DATABASE_URL"]
        env["JWT_SECRET_KEY"] = secrets.token_urlsafe(48)
        env["JWT_TTL_SECONDS"] = "1800"
        return subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_auth_*.py", "-v"],
            cwd=root, env=env,
        ).returncode
    finally:
        if started:
            subprocess.run(["docker", "rm", "--force", name], check=True, capture_output=True)


if __name__ == "__main__":
    raise SystemExit(main())

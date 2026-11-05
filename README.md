## 프로젝트 구조

기능별 도메인 내부에 presentation, application, domain, infrastructure의 4계층을 구성합니다.

폴더별 역할과 협업 규칙은 [프로젝트 구조 안내](docs/project-structure.md)를 참고하세요.

## 개발 서버 실행

회원/인증의 환경변수, API 계약과 검증 방법은 [회원과 인증 API](docs/users-auth.md)를 참고하세요.

프로젝트 루트에서 실행합니다. `--app-dir src`는 `src`를 모듈 검색 경로에 추가합니다.

```bash
uv run uvicorn main:app --app-dir src --reload
```

이미 `src` 폴더에 있다면 다음 명령으로 실행합니다.

```bash
uv run uvicorn main:app --reload
```

`[tool.uv]`의 `package = false`는 프로젝트 자체를 패키지로 빌드·설치하지 않도록 지정합니다. 실행 경로는 위 명령으로 지정합니다.

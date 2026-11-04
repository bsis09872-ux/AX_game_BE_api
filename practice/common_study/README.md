# common_study (by itme·inventory domain damdang)

공통 응답·예외 처리와 로깅을 직접 만들어 보며 공부한 모듈이다. 팀 코드에서는 사용하지 않는다(`src/`와 `main.py`에서 가져다 쓰지 않음).

## 들어 있는 것

| 파일                          | 내용                                                                                          |
| ----------------------------- | --------------------------------------------------------------------------------------------- |
| `common_study/exceptions.py`  | `AppError`와 자식 예외(400·401·403·404·422·429·503)                                           |
| `common_study/responses.py`   | `IdStr`(ID를 문자열로), `PageResponse`, `PageParams`                                          |
| `common_study/handlers.py`    | 예외를 `{"detail": {"code", "message"}}` 응답으로 바꾸는 핸들러, 도메인 계층 예외 대응표 등록 |
| `common_study/app_logging.py` | `get_logger`, `setup_logging`, 요청 로그 미들웨어                                             |
| `tests/`                      | `unittest` 테스트 53개                                                                        |

## 테스트 실행

저장소 루트에서 PowerShell로 실행한다.

```powershell
$env:PYTHONPATH='practice/common_study'
uv run python -m unittest discover -s practice/common_study/tests -t practice/common_study
```

`Ran 53 tests ... OK`가 나오면 정상이다.

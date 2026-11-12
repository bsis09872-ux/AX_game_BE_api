"""Swagger(/docs) 명세를 읽기 좋게 다듬는다.

- 브라우저 화면(HTML)과 쿠키 로그인 경로는 API 문서에서 숨긴다
- 태그에 한국어 설명을 붙이고, 공통 오류 응답({"detail": {"code", "message"}})을 문서에 넣는다
- 라우터 파일을 고치지 않고 앱 한 곳에서 처리한다. 라우터에서 오류를 직접 적고 싶으면 errors()를 쓴다
- /docs 는 환경변수 DOCS_ENABLED=false 로 끌 수 있다 (기본은 켜짐)
"""

import os
import re

from pydantic import BaseModel, ConfigDict


OPENAPI_DESCRIPTION = """낚시로 얻은 아이템을 경매장에서 거래하는 서비스의 JSON API입니다.

- **로그인:** `POST /v1/auth/token`으로 토큰을 받고, 오른쪽 위 **Authorize**에 아이디와 비밀번호를 넣으면 됩니다.
- **경로:** API는 모두 `/v1`로 시작합니다. 브라우저 화면(가방, 경매장 등)은 이 문서에 나오지 않습니다.
- **오류 형식:** 업무 오류는 `{"detail": {"code": "...", "message": "..."}}` 모양으로 응답합니다.
"""

OPENAPI_TAGS = [
    {"name": "auth", "description": "회원가입, 로그인, 토큰 갱신, 로그아웃"},
    {"name": "users", "description": "내 정보"},
    {"name": "inventory", "description": "내 아이템과 아이템 카탈로그 조회, 관리자 카탈로그 관리와 이력"},
    {"name": "fishing", "description": "낚시 보상 지급 (Bearer 토큰용)"},
    {"name": "wallet", "description": "지갑 잔액 조회와 관리자 충전"},
    {"name": "listings", "description": "경매 매물 조회, 등록, 입찰, 취소"},
    {"name": "trades", "description": "내 낙찰·판매 내역과 입찰 제한 상태"},
    {"name": "auction-management", "description": "관리자용 경매 매물·거래 조회와 강제 취소"},
    {"name": "admin-members", "description": "관리자용 회원 관리 (역할, 로그인 정지, 입찰 제한)"},
    {"name": "admin-auctions", "description": "관리자 경매 화면용"},
    {"name": "admin-web", "description": "관리자 화면이 쓰는 카탈로그·이미지 API (쿠키 로그인)"},
    {"name": "wallet-web", "description": "화면용 지갑 조회 (쿠키 로그인)"},
    {"name": "system", "description": "서버 상태 확인"},
]


# Swagger UI 화면 설정: 새로고침해도 로그인 유지, 처음엔 태그를 접어 두기, 검색 칸, 요청 시간 표시
SWAGGER_UI_PARAMETERS = {
    "persistAuthorization": True,
    "docExpansion": "none",
    "filter": True,
    "displayRequestDuration": True,
    "defaultModelsExpandDepth": -1,
}

_HANGUL = re.compile(r"[가-힣]")

# 라우터에 한국어 요약이 아직 없는 작업의 요약과 설명. 라우터가 한국어 summary를 달면 그쪽이 우선한다.
_OPERATION_TEXT = {
    ("POST", "/v1/auth/register"): ("회원 가입", "로그인 ID(소문자·숫자·밑줄 4~50자), 표시 이름, 비밀번호로 회원을 만듭니다."),
    ("POST", "/v1/auth/token"): ("로그인 (토큰 발급)", "폼의 `username`은 로그인 ID입니다. 오른쪽 위 Authorize가 이 경로를 사용합니다."),
    ("POST", "/v1/auth/refresh"): ("토큰 갱신", "refresh 토큰으로 새 토큰 쌍을 받습니다. 이미 쓴 refresh 토큰을 다시 쓰면 그 로그인 세션이 폐기됩니다."),
    ("POST", "/v1/auth/refresh/logout"): ("로그아웃 (refresh 토큰으로)", "access 토큰이 만료된 상태에서 refresh 토큰으로 로그인 세션을 폐기합니다."),
    ("POST", "/v1/auth/logout"): ("로그아웃", "현재 로그인 세션만 폐기합니다. 다른 기기의 세션은 유지됩니다."),
    ("GET", "/v1/users/me"): ("내 정보 조회", None),
    ("POST", "/v1/fishing-results"): ("낚시 보상 지급 (Bearer)", "검증된 투척(`cast_id`)에 보상을 지급합니다. 같은 `cast_id`로 다시 요청해도 중복 지급하지 않습니다."),
    ("GET", "/wallet/balance"): ("사용 가능 금액 조회 (화면용)", "헤더에 표시하는 사용 가능 금액만 돌려줍니다. 쿠키 로그인을 씁니다."),
    ("GET", "/admin/item-images"): ("사용할 수 있는 아이템 그림 목록 (관리자)", None),
    ("POST", "/admin/item-images"): ("아이템 그림 업로드 (관리자)", "PNG 파일 본문을 그대로 보냅니다. 2MB를 넘으면 413입니다."),
    ("GET", "/admin/item-catalogs"): ("카탈로그 목록 조회 (관리자)", "관리자 화면용입니다. 낚시 가중치와 `fishable`도 함께 보입니다."),
    ("POST", "/admin/item-catalogs"): ("카탈로그 생성 (관리자, 화면용)", None),
    ("GET", "/admin/item-catalogs/export.csv"): ("카탈로그 CSV 내보내기 (관리자)", None),
    ("PATCH", "/admin/item-catalogs/{definition_id}"): ("카탈로그 수정 (관리자, 화면용)", "보낸 항목만 바꿉니다. `name`과 `category`는 바꿀 수 없습니다."),
    ("DELETE", "/admin/item-catalogs/{definition_id}"): ("카탈로그 삭제 (관리자, 화면용)", "이미 아이템이 만들어진 카탈로그는 지울 수 없습니다."),
    ("GET", "/admin/inventory/{item_id}/events"): ("아이템 이력 조회 (관리자, 화면용)", "지급·예약·해제·이전 기록을 오래된 순으로 돌려줍니다."),
    ("POST", "/admin/member-accounts"): ("회원 계정 생성 (관리자)", "관리자가 직접 회원을 만듭니다."),
    ("PATCH", "/admin/member-accounts/{member_id}/role"): ("회원 역할 변경 (관리자)", "`USER` 또는 `ADMIN`으로 바꿉니다."),
    ("PATCH", "/admin/member-accounts/{member_id}/login-suspension"): ("회원 로그인 정지·해제 (관리자)", "정지하면 그 회원의 로그인 세션이 함께 폐기됩니다."),
    ("PATCH", "/admin/member-accounts/{member_id}/bid-restriction"): ("회원 입찰 제한 설정·해제 (관리자)", "`until`까지 새 입찰을 막습니다. `null`이면 제한을 풉니다."),
}


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    """공통 업무 오류 응답"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"detail": {"code": "ITEM_NOT_FOUND", "message": "아이템을 찾을 수 없습니다."}}
        }
    )

    detail: ErrorDetail


_ERROR_TEXT = {
    400: "요청 값이 규칙에 맞지 않음",
    401: "로그인이 필요하거나 토큰이 유효하지 않음",
    403: "권한이 없음",
    404: "대상을 찾을 수 없음",
    409: "현재 상태에서는 처리할 수 없음",
}


def errors(*codes: int) -> dict:
    """라우터의 responses= 에 넣는 공통 오류 응답. 예: responses=errors(401, 404)"""
    return {code: {"model": ErrorResponse, "description": _ERROR_TEXT[code]} for code in codes}


def read_docs_urls() -> dict:
    """DOCS_ENABLED가 꺼짐이면 /docs, /redoc, /openapi.json을 모두 비활성화한다."""
    value = os.environ.get("DOCS_ENABLED", "true").strip().lower()
    if value in ("0", "false", "no", "off"):
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}


# 쿠키 로그인 화면에서만 쓰는 경로. 응답이 HTML이 아니라서 따로 숨긴다.
_COOKIE_WEB_PATHS = {"/login", "/register", "/session", "/session/refresh", "/logout"}
_SCREEN_PREFIXES = ("/v1/play",)  # 낚시터 화면이 WebSocket 연결과 함께 쓰는 경로
_ADMIN_TAGS = {"admin-web", "admin-auctions", "admin-members", "auction-management"}
_METHODS = {"get", "post", "put", "patch", "delete"}


def _success_types(operation: dict) -> set:
    types = set()
    for code, response in operation.get("responses", {}).items():
        if str(code).startswith("2"):
            types |= set(response.get("content", {}))
    return types


def _is_screen(path: str, operation: dict) -> bool:
    types = _success_types(operation)
    html_only = "text/html" in types and "application/json" not in types
    return html_only or path in _COOKIE_WEB_PATHS or path.startswith(_SCREEN_PREFIXES)


def _add_errors(path: str, method: str, operation: dict) -> None:
    wanted = []
    if operation.get("security"):
        wanted.append(401)
    tags = set(operation.get("tags", []))
    if "/admin" in path or "/management" in path or tags & _ADMIN_TAGS:
        wanted.append(403)
    if method in ("get", "patch", "delete") and "{" in path:
        wanted.append(404)
    responses = operation.setdefault("responses", {})
    for code in wanted:
        responses.setdefault(
            str(code),
            {
                "description": _ERROR_TEXT[code],
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
            },
        )


def _apply_text(path: str, method: str, operation: dict) -> None:
    text = _OPERATION_TEXT.get((method.upper(), path))
    if text is None or _HANGUL.search(operation.get("summary", "")):
        return
    operation["summary"] = text[0]
    if text[1] and not operation.get("description"):
        operation["description"] = text[1]


def _unify_security(schema: dict) -> None:
    """HTTPBearer(토큰 붙여넣기)를 OAuth2PasswordBearer(로그인)로 합쳐 Authorize를 한 번만 하게 한다.
    두 방식 모두 같은 Bearer 헤더를 쓰므로 실제 인증 동작은 달라지지 않는다."""
    for operations in schema["paths"].values():
        for operation in operations.values():
            if not isinstance(operation, dict) or "security" not in operation:
                continue
            merged = []
            for requirement in operation["security"]:
                renamed = {("OAuth2PasswordBearer" if k == "HTTPBearer" else k): v for k, v in requirement.items()}
                if renamed not in merged:
                    merged.append(renamed)
            operation["security"] = merged
    schemes = schema.get("components", {}).get("securitySchemes", {})
    if "OAuth2PasswordBearer" in schemes:
        schemes.pop("HTTPBearer", None)


def _error_status(cls: type) -> int | None:
    """exception_handlers가 응답으로 바꾸는 상태 번호. 분류되지 않은 오류는 500이라 표에서 뺀다."""
    from shared.core.exceptions import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError

    if any(base.__name__ == "AuthenticationError" for base in cls.__mro__):
        return 401  # 인증 오류는 auth의 전용 핸들러가 401로 바꾼다
    for base, status in ((BusinessRuleError, 400), (NotFoundError, 404), (ConflictError, 409), (ForbiddenError, 403)):
        if issubclass(cls, base):
            return status
    return None


def _all_subclasses(cls: type):
    for sub in cls.__subclasses__():
        yield sub
        yield from _all_subclasses(sub)


def _add_error_table(schema: dict) -> None:
    """코드의 오류 클래스에서 오류 코드 표를 만들어 소개 아래에 붙인다. 코드가 바뀌면 문서도 따라 바뀐다."""
    from shared.core.exceptions import AppError

    rows = {}
    for cls in (AppError, *_all_subclasses(AppError)):
        status = _error_status(cls)
        if status is None or "code" not in cls.__dict__:
            continue
        rows[cls.code] = (status, cls.message)
    if not rows:
        return
    lines = ["", "## 오류 코드", "", "| 상태 | 코드 | 기본 메시지 |", "| --- | --- | --- |"]
    for code, (status, message) in sorted(rows.items(), key=lambda item: (item[1][0], item[0])):
        lines.append(f"| {status} | `{code}` | {message} |")
    table = chr(10).join(lines)
    schema["info"]["description"] = schema["info"].get("description", "").rstrip() + chr(10) + table + chr(10)


def _postprocess(schema: dict) -> None:
    used_tags = set()
    for path in list(schema["paths"]):
        operations = schema["paths"][path]
        for method in list(operations):
            if method not in _METHODS:
                continue
            operation = operations[method]
            if _is_screen(path, operation):
                del operations[method]
                continue
            _apply_text(path, method, operation)
            _add_errors(path, method, operation)
            used_tags |= set(operation.get("tags", []))
        if not any(m in _METHODS for m in operations):
            del schema["paths"][path]

    _unify_security(schema)
    _add_error_table(schema)

    models = schema.setdefault("components", {}).setdefault("schemas", {})
    detail = ErrorResponse.model_json_schema(ref_template="#/components/schemas/{model}")
    models.update(detail.pop("$defs", {}))
    models["ErrorResponse"] = detail
    if "tags" in schema:
        schema["tags"] = [tag for tag in schema["tags"] if tag["name"] in used_tags]


def install_openapi(app) -> None:
    """앱의 명세를 처음 만들 때 한 번 다듬는다. 모든 라우터를 등록한 뒤 호출한다."""
    original = app.openapi
    done = {"value": False}

    def openapi() -> dict:
        schema = original()
        if not done["value"]:
            _postprocess(schema)
            done["value"] = True
        return schema

    app.openapi = openapi

"""inventory 파일 점검 테스트

- 계층별로 필요한 파일이 모두 있는지
- 각 파일 맨 위에 설명(docstring)이 있는지 (한 줄 요약 + 규칙이나 금지 사항)
- domain 계층 파일이 FastAPI, Pydantic, SQLAlchemy, logging을 import하지 않는지
"""

import ast
import unittest
from pathlib import Path

INVENTORY_DIR = Path(__file__).resolve().parents[2] / "src" / "inventory"

EXPECTED_FILES = [
    "domain/enums.py",
    "domain/exceptions.py",
    "domain/item_definition.py",
    "domain/inventory_item.py",
    "domain/item_event.py",
    "application/service.py",
    "infrastructure/models.py",
    "infrastructure/repositories.py",
    "presentation/schemas.py",
    "presentation/router.py",
    "presentation/dependencies.py",
]
FORBIDDEN_IN_DOMAIN = {"fastapi", "starlette", "pydantic", "sqlalchemy", "logging"}
# 한 줄 요약 + 빈 줄 + 규칙이나 금지 사항 한 줄 이상
MIN_DOCSTRING_LINES = 3


def parse(relative_path: str) -> ast.Module:
    source = (INVENTORY_DIR / relative_path).read_text(encoding="utf-8")
    return ast.parse(source)


def imported_top_modules(tree: ast.Module) -> set[str]:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


class InventoryFileCommentsTest(unittest.TestCase):
    def test_all_expected_files_exist(self):
        for relative_path in EXPECTED_FILES:
            with self.subTest(file=relative_path):
                self.assertTrue((INVENTORY_DIR / relative_path).is_file())

    def test_every_file_starts_with_docstring(self):
        for relative_path in EXPECTED_FILES:
            if not (INVENTORY_DIR / relative_path).is_file():
                continue  # 없는 파일은 위 테스트가 알려 준다
            with self.subTest(file=relative_path):
                docstring = ast.get_docstring(parse(relative_path))
                self.assertTrue(docstring, "맨 위에 docstring이 없다")
                self.assertGreaterEqual(
                    len(docstring.splitlines()),
                    MIN_DOCSTRING_LINES,
                    "한 줄 요약 뒤에 규칙이나 금지 사항이 있어야 한다",
                )

    def test_domain_files_do_not_import_framework_or_logging(self):
        for relative_path in EXPECTED_FILES:
            if not relative_path.startswith("domain/"):
                continue
            if not (INVENTORY_DIR / relative_path).is_file():
                continue
            with self.subTest(file=relative_path):
                used = imported_top_modules(parse(relative_path))
                self.assertEqual(used & FORBIDDEN_IN_DOMAIN, set())


if __name__ == "__main__":
    unittest.main()

import ast
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "src"


def imports(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


class DependencyBoundaryTests(unittest.TestCase):
    def test_users_does_not_import_auth(self):
        for path in (SOURCE / "users").rglob("*.py"):
            for module in imports(path):
                with self.subTest(path=str(path), module=module):
                    self.assertNotEqual(module.split(".")[0], "auth")

    def test_core_layers_do_not_import_web_database_or_outer_layers(self):
        technologies = {"fastapi", "starlette", "pydantic", "sqlalchemy", "asyncpg", "database", "jwt", "passlib"}
        for context in ("auth", "users", "auction", "inventory", "wallet"):
            for layer in ("domain", "application"):
                for path in (SOURCE / context / layer).rglob("*.py"):
                    for module in imports(path):
                        parts = module.split(".")
                        with self.subTest(path=str(path), module=module):
                            self.assertNotIn(parts[0], technologies)
                            self.assertTrue({"presentation", "infrastructure", "wiring"}.isdisjoint(parts))
                            if layer == "domain":
                                self.assertNotIn("application", parts)


if __name__ == "__main__":
    unittest.main()

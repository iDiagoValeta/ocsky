"""The import and call rules of the hexagonal layers, checked with ast over the source tree."""
from __future__ import annotations

import ast
import os
import tempfile
import unittest

from tests import helpers  # noqa: F401

CORE_ALLOWED = {"__future__", "dataclasses", "typing", "json", "hashlib", "math", "unicodedata"}
DRIVEN = "ocsky.adapters.driven"
DRIVING = "ocsky.adapters.driving"


def _under(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


def _core_import_allowed(name: str) -> bool:
    return name.split(".")[0] in CORE_ALLOWED or _under(name, "ocsky.core")


def _imported_names(tree: ast.AST, module_parts: list[str], is_package: bool) -> list[tuple[int, str]]:
    """(line, absolute dotted name) of every import. `from x import a` yields `x.a`, so an imported
    package is checked through what it brings in. Relative imports are resolved against the module."""
    package = module_parts if is_package else module_parts[:-1]
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = package[: max(0, len(package) - (node.level - 1))] if node.level else []
            prefix = base + (node.module.split(".") if node.module else [])
            for alias in node.names:
                name = ".".join(prefix) if alias.name == "*" else ".".join(prefix + [alias.name])
                found.append((node.lineno, name))
    return found


def violations(root: str) -> list[str]:
    """Every rule broken under root/src/ocsky, as 'path:line: message'. Empty when the layers hold."""
    src = os.path.join(root, "src")
    found: list[str] = []
    for dirpath, _, files in os.walk(os.path.join(src, "ocsky")):
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, src).replace(os.sep, "/")
            parts = rel[:-3].split("/")
            is_package = parts[-1] == "__init__"
            module_parts = parts[:-1] if is_package else parts
            module = ".".join(module_parts)
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=path)
            imports = _imported_names(tree, module_parts, is_package)

            if _under(module, "ocsky.core"):
                for line, imported in imports:
                    if not _core_import_allowed(imported):
                        found.append(f"{rel}:{line}: core imports {imported}")
                for node in ast.walk(tree):
                    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                            and node.func.id == "open"):
                        found.append(f"{rel}:{node.lineno}: core calls open()")

            if _under(module, DRIVEN):
                found.extend(f"{rel}:{line}: driven imports {imp}" for line, imp in imports
                             if _under(imp, DRIVING))
            if _under(module, DRIVING):
                found.extend(f"{rel}:{line}: driving imports {imp}" for line, imp in imports
                             if _under(imp, DRIVEN))

            if rel != "ocsky/main.py":
                names = [imp for _, imp in imports]
                if any(_under(n, DRIVEN) for n in names) and any(_under(n, DRIVING) for n in names):
                    found.append(f"{rel}: imports both adapter families (only main.py may)")
    return found


class ArchitectureRulesTest(unittest.TestCase):
    def test_the_real_source_tree_follows_every_import_rule(self):
        self.assertEqual(violations(helpers.ROOT), [])

    @unittest.skipUnless(os.path.exists(os.path.join(helpers.SRC, "ocsky", "main.py")),
                         "main.py does not exist yet")
    def test_only_the_composition_root_imports_both_adapter_families(self):
        both = [v for v in violations(helpers.ROOT) if "both adapter families" in v]
        self.assertEqual(both, [])

    def test_the_checker_reports_a_planted_sqlite_import_in_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = os.path.join(tmp, "src", "ocsky", "core")
            os.makedirs(core)
            with open(os.path.join(core, "bad.py"), "w", encoding="utf-8") as f:
                f.write("from __future__ import annotations\nimport sqlite3\n")
            found = violations(tmp)
        self.assertTrue(any("bad.py:2" in v and "sqlite3" in v for v in found), found)

    def test_the_checker_reports_a_planted_open_call_in_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = os.path.join(tmp, "src", "ocsky", "core")
            os.makedirs(core)
            with open(os.path.join(core, "bad.py"), "w", encoding="utf-8") as f:
                f.write("from __future__ import annotations\n\ndef read():\n    return open('x')\n")
            found = violations(tmp)
        self.assertTrue(any("core calls open()" in v for v in found), found)

    def test_the_checker_reports_a_planted_import_between_adapter_families(self):
        with tempfile.TemporaryDirectory() as tmp:
            driven = os.path.join(tmp, "src", "ocsky", "adapters", "driven")
            os.makedirs(driven)
            with open(os.path.join(driven, "bad.py"), "w", encoding="utf-8") as f:
                f.write("from ocsky.adapters import driving\n")
            found = violations(tmp)
        self.assertTrue(any("driven imports ocsky.adapters.driving" in v for v in found), found)


if __name__ == "__main__":
    unittest.main()

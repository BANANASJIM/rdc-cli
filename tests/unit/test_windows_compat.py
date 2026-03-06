"""Regression tests for Windows compatibility.

Scans the codebase to prevent reintroduction of Windows-incompatible
patterns fixed in Phase W4.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).parent.parent.parent / "src" / "rdc"


class TestAsciiOutput:
    """Ensure CLI output contains only ASCII-safe characters (B60/B61/B66).

    Windows cp1252 terminals crash on Unicode above U+00FF. All user-facing
    output must use ASCII substitutes.
    """

    _FORBIDDEN_RANGES = [
        (0x2500, 0x257F, "box-drawing"),
        (0x2190, 0x21FF, "arrows"),
        (0x2600, 0x27BF, "misc symbols"),
        (0x1F300, 0x1F9FF, "emoji"),
        (0x2013, 0x2014, "em/en dash"),
    ]

    @staticmethod
    def _docstring_lines(tree: ast.AST) -> set[int]:
        """Collect line numbers of all docstrings (module/class/function)."""
        lines: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    lines.add(node.body[0].value.lineno)
        return lines

    def _scan_python_strings(self) -> list[tuple[Path, int, str, str]]:
        violations: list[tuple[Path, int, str, str]] = []
        for py_file in sorted(SRC_DIR.rglob("*.py")):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            skip = self._docstring_lines(tree)
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.lineno in skip:
                        continue
                    for char in node.value:
                        code = ord(char)
                        for lo, hi, desc in self._FORBIDDEN_RANGES:
                            if lo <= code <= hi:
                                violations.append(
                                    (
                                        py_file.relative_to(SRC_DIR.parent.parent),
                                        node.lineno,
                                        char,
                                        desc,
                                    )
                                )
                                break
        return violations

    def test_no_forbidden_unicode_in_source(self) -> None:
        violations = self._scan_python_strings()
        if violations:
            lines = [f"  {f}:{line} U+{ord(c):04X} ({desc})" for f, line, c, desc in violations]
            pytest.fail("Forbidden Unicode in source strings:\n" + "\n".join(lines))


class TestNoOsPath:
    """Ensure no os.path usage in source code (pathlib.Path is project standard)."""

    def test_no_os_path_imports(self) -> None:
        violations: list[tuple[Path, int]] = []
        for py_file in sorted(SRC_DIR.rglob("*.py")):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "os.path":
                    violations.append((py_file.relative_to(SRC_DIR.parent.parent), node.lineno))
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "os.path":
                            rel = py_file.relative_to(SRC_DIR.parent.parent)
                            violations.append((rel, node.lineno))
        if violations:
            lines = [f"  {f}:{line}" for f, line in violations]
            pytest.fail("os.path imports found (use pathlib.Path):\n" + "\n".join(lines))


class TestNoPrintInSource:
    """Ensure no print() calls in source code (use click.echo or logging)."""

    _ALLOWED = {"discover.py"}

    def test_no_print_calls(self) -> None:
        violations: list[tuple[Path, int]] = []
        for py_file in sorted(SRC_DIR.rglob("*.py")):
            if py_file.name in self._ALLOWED:
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "print"
                ):
                    violations.append((py_file.relative_to(SRC_DIR.parent.parent), node.lineno))
        if violations:
            lines = [f"  {f}:{line}" for f, line in violations]
            pytest.fail("print() calls found (use click.echo()):\n" + "\n".join(lines))


class TestNoShellTrue:
    """Ensure no subprocess calls use shell=True (security + Windows compat)."""

    def test_no_shell_true(self) -> None:
        violations: list[tuple[Path, int]] = []
        for py_file in sorted(SRC_DIR.rglob("*.py")):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    for kw in node.keywords:
                        if (
                            kw.arg == "shell"
                            and isinstance(kw.value, ast.Constant)
                            and kw.value.value is True
                        ):
                            rel = py_file.relative_to(SRC_DIR.parent.parent)
                            violations.append((rel, node.lineno))
        if violations:
            lines = [f"  {f}:{line}" for f, line in violations]
            pytest.fail("shell=True found in subprocess calls:\n" + "\n".join(lines))


class TestUnicodePathSafety:
    """B77: click.echo must not crash on non-cp1252 characters in paths."""

    def test_fix_win_encoding_reconfigures_on_win32(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Regression: _fix_win_encoding must set errors='replace' on Windows."""
        import io
        import sys as real_sys

        from rdc.cli import _fix_win_encoding

        out = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
        err = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
        monkeypatch.setattr(real_sys, "platform", "win32")
        monkeypatch.setattr(real_sys, "stdout", out)
        monkeypatch.setattr(real_sys, "stderr", err)

        _fix_win_encoding()

        assert out.errors == "replace"
        assert err.errors == "replace"

    def test_fix_win_encoding_noop_on_linux(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_fix_win_encoding must not touch streams on non-Windows."""
        import io
        import sys as real_sys

        from rdc.cli import _fix_win_encoding

        buf = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", errors="strict")
        monkeypatch.setattr(real_sys, "platform", "linux")
        monkeypatch.setattr(real_sys, "stdout", buf)
        monkeypatch.setattr(real_sys, "stderr", buf)

        _fix_win_encoding()

        assert buf.errors == "strict"

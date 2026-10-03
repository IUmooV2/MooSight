#!/usr/bin/env python3
"""Find mutable class-level state that can leak across instances.

Legacy SpiderFoot contains several classes that define ``list()``, ``dict()``,
``set()``, or mutable literals at class scope. Unless that state is deliberately
shared, it can leak data between scans, tests, or concurrent instances.

This audit is intentionally static and network-free. It reports candidates for
manual review rather than rewriting code automatically.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_MUTABLE_CALLS = {"list", "dict", "set", "bytearray", "deque", "defaultdict"}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    class_name: str
    attribute: str
    expression: str


def _is_mutable_expr(node: ast.AST) -> bool:
    if isinstance(node, (ast.List, ast.Dict, ast.Set)):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id in _MUTABLE_CALLS
    return False


def _render_expr(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return node.__class__.__name__


def scan_source(source: str, path: str = "<memory>") -> list[Finding]:
    tree = ast.parse(source, filename=path)
    findings: list[Finding] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for statement in node.body:
            targets: list[ast.expr] = []
            value: ast.AST | None = None

            if isinstance(statement, ast.Assign):
                targets = list(statement.targets)
                value = statement.value
            elif isinstance(statement, ast.AnnAssign):
                targets = [statement.target]
                value = statement.value

            if value is None or not _is_mutable_expr(value):
                continue

            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                findings.append(Finding(
                    path=path,
                    line=getattr(statement, "lineno", 0),
                    class_name=node.name,
                    attribute=target.id,
                    expression=_render_expr(value),
                ))

    return findings


def iter_python_files(root: Path) -> Iterable[Path]:
    excluded = {".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache", ".ruff_cache"}
    for path in root.rglob("*.py"):
        if any(part in excluded for part in path.parts):
            continue
        yield path


def scan_repository(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_python_files(root):
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        try:
            findings.extend(scan_source(source, str(path.relative_to(root))))
        except SyntaxError:
            # Syntax failures are covered by the regular test/lint pipeline.
            continue
    return sorted(findings, key=lambda item: (item.path, item.line, item.class_name, item.attribute))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="repository root")
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="return a non-zero exit status when mutable class-state candidates are found",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    findings = scan_repository(root)

    for finding in findings:
        print(
            f"{finding.path}:{finding.line}: {finding.class_name}.{finding.attribute} "
            f"uses class-level mutable state ({finding.expression})"
        )

    print(f"\nMutable class-state candidates: {len(findings)}")
    return 1 if args.fail_on_findings and findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

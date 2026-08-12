#!/usr/bin/env python3
"""Audit Python code for overly broad exception handlers.

The scanner is intentionally static and network-free. It flags ``except
BaseException`` and bare ``except:`` handlers because both can swallow process
control exceptions such as ``KeyboardInterrupt`` and ``SystemExit``. Broad
``except Exception`` handlers are reported separately as review items rather
than hard failures because some legacy boundaries legitimately need them.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path


_EXCLUDED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__"}


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    line: int
    kind: str
    detail: str


def _handler_name(handler_type: ast.expr | None) -> str | None:
    if handler_type is None:
        return None
    if isinstance(handler_type, ast.Name):
        return handler_type.id
    if isinstance(handler_type, ast.Attribute):
        parts: list[str] = []
        node: ast.expr = handler_type
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        return ".".join(reversed(parts)) if parts else None
    return None


def audit_source(source: str, path: str = "<memory>") -> list[Finding]:
    tree = ast.parse(source, filename=path)
    findings: list[Finding] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue

        name = _handler_name(node.type)
        if name is None:
            findings.append(Finding(path, node.lineno, "bare-except", "bare except catches process-control exceptions"))
        elif name == "BaseException" or name.endswith(".BaseException"):
            findings.append(Finding(path, node.lineno, "base-exception", "BaseException catches KeyboardInterrupt and SystemExit"))
        elif name == "Exception" or name.endswith(".Exception"):
            findings.append(Finding(path, node.lineno, "broad-exception", "broad Exception handler should be reviewed and narrowed when practical"))

    return sorted(findings)


def audit_repository(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    root = root.resolve()

    for path in sorted(root.rglob("*.py")):
        if any(part in _EXCLUDED_DIRS for part in path.parts):
            continue
        try:
            source = path.read_text(encoding="utf-8")
            relative = str(path.relative_to(root))
            findings.extend(audit_source(source, relative))
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            relative = str(path.relative_to(root))
            findings.append(Finding(relative, 0, "audit-error", f"could not audit file: {exc.__class__.__name__}"))

    return sorted(findings)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit MooSight Python exception handling")
    parser.add_argument("root", nargs="?", default=".", help="repository root")
    parser.add_argument(
        "--fail-on-review",
        action="store_true",
        help="also fail for broad Exception review findings",
    )
    args = parser.parse_args()

    findings = audit_repository(Path(args.root))
    for finding in findings:
        print(f"{finding.path}:{finding.line}: {finding.kind}: {finding.detail}")

    blockers = {"bare-except", "base-exception", "audit-error"}
    if args.fail_on_review:
        blockers.add("broad-exception")

    blocking_count = sum(finding.kind in blockers for finding in findings)
    review_count = sum(finding.kind == "broad-exception" for finding in findings)
    print(f"\nException audit: {blocking_count} blocking, {review_count} review finding(s)")
    return 1 if blocking_count else 0


if __name__ == "__main__":
    raise SystemExit(main())

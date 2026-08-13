#!/usr/bin/env python3
"""Static security audit for high-risk legacy patterns in MooSight.

The audit is intentionally lightweight and dependency-free. It does not replace
Bandit, CodeQL, or human review. Its job is to make a few project-specific
security regressions visible during modernization.
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int
    message: str


class SecurityVisitor(ast.NodeVisitor):
    """Find project-specific Python security patterns without executing code."""

    def __init__(self, path: Path, root: Path) -> None:
        self.path = path
        self.root = root
        self.findings: list[Finding] = []

    def add(self, rule: str, node: ast.AST, message: str) -> None:
        self.findings.append(
            Finding(
                rule=rule,
                path=self.path.relative_to(self.root).as_posix(),
                line=getattr(node, "lineno", 1),
                message=message,
            )
        )

    @staticmethod
    def _call_name(node: ast.Call) -> str:
        parts: list[str] = []
        current = node.func
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Attribute):
                name = self._attribute_name(target)
                if name == "ssl._create_default_https_context":
                    self.add(
                        "TLS_GLOBAL_CONTEXT",
                        node,
                        "Do not replace Python's process-wide HTTPS context; scope TLS behavior to a request/session.",
                    )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        call_name = self._call_name(node)

        if call_name.endswith("disable_warnings"):
            self.add(
                "TLS_GLOBAL_WARNING_SUPPRESSION",
                node,
                "Global insecure-request warning suppression hides unrelated TLS failures.",
            )

        if call_name.endswith(("get", "post", "head", "request")):
            for keyword in node.keywords:
                if keyword.arg == "verify" and isinstance(keyword.value, ast.Constant) and keyword.value.value is False:
                    self.add(
                        "TLS_VERIFY_FALSE",
                        node,
                        "Explicit verify=False requires a documented, narrowly scoped OSINT reason.",
                    )

        if call_name in {"subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_output"}:
            for keyword in node.keywords:
                if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                    self.add(
                        "SUBPROCESS_SHELL_TRUE",
                        node,
                        "shell=True increases command-injection risk and should be avoided or tightly justified.",
                    )

        self.generic_visit(node)

    @staticmethod
    def _attribute_name(node: ast.Attribute) -> str:
        parts: list[str] = []
        current: ast.AST = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))


def iter_python_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def audit(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_python_files(root):
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            findings.append(
                Finding(
                    rule="AUDIT_PARSE_ERROR",
                    path=path.relative_to(root).as_posix(),
                    line=getattr(exc, "lineno", 1) or 1,
                    message=f"Could not inspect file: {type(exc).__name__}",
                )
            )
            continue

        visitor = SecurityVisitor(path, root)
        visitor.visit(tree)
        findings.extend(visitor.findings)

    return sorted(findings, key=lambda item: (item.path, item.line, item.rule))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Return exit code 1 when findings exist. Keep off while reducing the legacy baseline.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    findings = audit(root)

    if args.as_json:
        print(json.dumps([asdict(item) for item in findings], indent=2))
    else:
        if not findings:
            print("No project-specific security findings detected.")
        for item in findings:
            print(f"{item.path}:{item.line}: {item.rule}: {item.message}")
        print(f"\nFindings: {len(findings)}")

    return 1 if findings and args.fail_on_findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

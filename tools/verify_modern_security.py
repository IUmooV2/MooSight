#!/usr/bin/env python3
"""Enforce project-specific security rules on MooSight-owned modern code.

Legacy SpiderFoot still contains historical security patterns that are being
retired incrementally. This verifier prevents those patterns from entering or
re-entering MooSight's modern runtime while that cleanup continues.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from tools.audit_security import Finding, SecurityVisitor
from tools.modern_files import MODERN_PYTHON_FILES


BLOCKING_RULES = {
    "TLS_GLOBAL_CONTEXT",
    "TLS_GLOBAL_WARNING_SUPPRESSION",
    "SUBPROCESS_SHELL_TRUE",
    "AUDIT_PARSE_ERROR",
}
REVIEW_RULES = {"TLS_VERIFY_FALSE"}


@dataclass(frozen=True)
class SecurityPolicyResult:
    findings: tuple[Finding, ...]
    missing_files: tuple[str, ...]

    @property
    def blockers(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.rule in BLOCKING_RULES)

    @property
    def review_findings(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.rule in REVIEW_RULES)

    @property
    def ok(self) -> bool:
        return not self.blockers and not self.missing_files


def verify_modern_security(root: Path) -> SecurityPolicyResult:
    root = root.resolve()
    findings: list[Finding] = []
    missing: list[str] = []

    for relative in MODERN_PYTHON_FILES:
        path = root / relative
        if not path.is_file():
            missing.append(relative)
            continue

        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            findings.append(
                Finding(
                    rule="AUDIT_PARSE_ERROR",
                    path=relative,
                    line=getattr(exc, "lineno", 1) or 1,
                    message=f"Could not inspect file: {type(exc).__name__}",
                )
            )
            continue

        visitor = SecurityVisitor(path, root)
        visitor.visit(tree)
        findings.extend(visitor.findings)

    ordered = tuple(sorted(findings, key=lambda item: (item.path, item.line, item.rule)))
    return SecurityPolicyResult(ordered, tuple(sorted(missing)))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    result = verify_modern_security(root)

    for missing in result.missing_files:
        print(f"[FAIL] missing modern security file: {missing}")

    for finding in result.findings:
        level = "FAIL" if finding.rule in BLOCKING_RULES else "REVIEW"
        print(f"[{level}] {finding.path}:{finding.line}: {finding.rule}: {finding.message}")

    print(
        f"\nModern security policy: {len(result.blockers)} blocking, "
        f"{len(result.review_findings)} review, "
        f"{len(result.missing_files)} missing file(s)"
    )
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

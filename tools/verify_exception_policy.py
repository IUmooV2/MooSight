#!/usr/bin/env python3
"""Enforce exception-handling policy on MooSight-owned modern code.

Legacy SpiderFoot still contains broad historical handlers. This verifier draws
an explicit boundary around newly introduced MooSight code so bare ``except``
and ``BaseException`` handlers cannot regress into the modernized runtime while
legacy cleanup continues incrementally.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tools.exception_audit import Finding, audit_source


MODERN_FILES = (
    "moosight.py",
    "spiderfoot/config.py",
    "spiderfoot/http_client.py",
    "spiderfoot/legacy_fetch.py",
    "spiderfoot/modern_core.py",
    "spiderfoot/modern_network_mixin.py",
    "spiderfoot/modern_scanner.py",
    "spiderfoot/network.py",
    "spiderfoot/network_legacy.py",
    "spiderfoot/security.py",
    "spiderfoot/tls.py",
    "tools/audit_mutable_class_state.py",
    "tools/audit_security.py",
    "tools/exception_audit.py",
    "tools/preflight.py",
    "tools/verify_modern_runtime.py",
    "tools/verify_exception_policy.py",
)

BLOCKING_KINDS = {"bare-except", "base-exception", "audit-error"}


@dataclass(frozen=True)
class PolicyResult:
    findings: tuple[Finding, ...]
    missing_files: tuple[str, ...]

    @property
    def blockers(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.kind in BLOCKING_KINDS)

    @property
    def ok(self) -> bool:
        return not self.blockers and not self.missing_files


def verify_exception_policy(root: Path) -> PolicyResult:
    root = root.resolve()
    findings: list[Finding] = []
    missing: list[str] = []

    for relative in MODERN_FILES:
        path = root / relative
        if not path.is_file():
            missing.append(relative)
            continue
        try:
            source = path.read_text(encoding="utf-8")
            findings.extend(audit_source(source, relative))
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            findings.append(
                Finding(relative, 0, "audit-error", f"could not audit file: {exc.__class__.__name__}")
            )

    return PolicyResult(tuple(sorted(findings)), tuple(sorted(missing)))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    result = verify_exception_policy(root)

    for missing in result.missing_files:
        print(f"[FAIL] missing modern policy file: {missing}")

    for finding in result.findings:
        level = "FAIL" if finding.kind in BLOCKING_KINDS else "REVIEW"
        print(f"[{level}] {finding.path}:{finding.line}: {finding.kind}: {finding.detail}")

    print(
        f"\nModern exception policy: {len(result.blockers)} blocking, "
        f"{sum(f.kind == 'broad-exception' for f in result.findings)} review, "
        f"{len(result.missing_files)} missing file(s)"
    )
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

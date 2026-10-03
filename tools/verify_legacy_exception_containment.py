#!/usr/bin/env python3
"""Verify MooSight overrides legacy methods with unsafe exception handlers.

This is a migration guard for ``sflib.SpiderFoot``. It statically identifies
legacy methods containing bare ``except`` or ``except BaseException`` handlers
and confirms the active ``ModernSpiderFoot`` class resolves those method names
to an implementation outside the legacy class.

The legacy source can therefore remain available during incremental migration
without silently re-exposing known process-control exception swallowing through
the normal MooSight runtime.
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from pathlib import Path

from sflib import SpiderFoot as LegacySpiderFoot
from spiderfoot.modern_core import ModernSpiderFoot


@dataclass(frozen=True, order=True)
class LegacyRisk:
    method: str
    line: int
    kind: str


@dataclass(frozen=True)
class ContainmentResult:
    risks: tuple[LegacyRisk, ...]
    uncontained: tuple[LegacyRisk, ...]

    @property
    def ok(self) -> bool:
        return not self.uncontained


def _is_base_exception(expr: ast.expr | None) -> bool:
    if isinstance(expr, ast.Name):
        return expr.id == "BaseException"
    if isinstance(expr, ast.Attribute):
        return expr.attr == "BaseException"
    return False


def find_legacy_exception_risks(source: str) -> list[LegacyRisk]:
    """Return methods containing bare or BaseException handlers."""
    tree = ast.parse(source)
    risks: list[LegacyRisk] = []

    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "SpiderFoot":
            continue
        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for nested in ast.walk(item):
                if not isinstance(nested, ast.ExceptHandler):
                    continue
                if nested.type is None:
                    risks.append(LegacyRisk(item.name, nested.lineno, "bare-except"))
                elif _is_base_exception(nested.type):
                    risks.append(LegacyRisk(item.name, nested.lineno, "base-exception"))
    return sorted(set(risks))


def method_is_overridden(method_name: str) -> bool:
    """Return True when ModernSpiderFoot resolves a method before legacy class."""
    for cls in ModernSpiderFoot.__mro__:
        if method_name in cls.__dict__:
            return cls is not LegacySpiderFoot
    return False


def verify_containment(source: str | None = None) -> ContainmentResult:
    if source is None:
        source = inspect.getsource(LegacySpiderFoot)
    risks = tuple(find_legacy_exception_risks(source))
    uncontained = tuple(risk for risk in risks if not method_is_overridden(risk.method))
    return ContainmentResult(risks=risks, uncontained=uncontained)


def main() -> int:
    result = verify_containment()
    grouped: dict[str, set[str]] = {}
    for risk in result.risks:
        grouped.setdefault(risk.method, set()).add(risk.kind)

    for method in sorted(grouped):
        contained = method not in {risk.method for risk in result.uncontained}
        status = "PASS" if contained else "FAIL"
        kinds = ", ".join(sorted(grouped[method]))
        print(f"[{status}] {method}: legacy {kinds} handler(s) are {'overridden' if contained else 'reachable'}")

    print(
        f"\nLegacy exception containment: "
        f"{len(result.risks) - len(result.uncontained)}/{len(result.risks)} risky handler occurrence(s) contained"
    )
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Verify MooSight's modern runtime routing and security invariants.

This check is intentionally local and network-free. It proves that the normal
MooSight entry point routes core construction through ``ModernSpiderFoot`` and
that constructing the core does not leave Python's process-wide HTTPS context
weakened.
"""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from typing import Callable

import moosight
import sf
import sfscan
from spiderfoot.modern_core import ModernSpiderFoot
from spiderfoot.modern_network_mixin import ModernNetworkMixin


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def _result(name: str, condition: bool, success: str, failure: str) -> Check:
    return Check(name=name, ok=condition, detail=success if condition else failure)


def verify_runtime() -> list[Check]:
    checks: list[Check] = []

    moosight.install_modern_core()
    checks.append(_result(
        "main core routing",
        sf.SpiderFoot is ModernSpiderFoot,
        "sf.py is routed to ModernSpiderFoot",
        "sf.py is not routed to ModernSpiderFoot",
    ))
    checks.append(_result(
        "scanner core routing",
        sfscan.SpiderFoot is ModernSpiderFoot,
        "sfscan.py is routed to ModernSpiderFoot",
        "sfscan.py is not routed to ModernSpiderFoot",
    ))

    mro = ModernSpiderFoot.__mro__
    checks.append(_result(
        "network method precedence",
        ModernNetworkMixin in mro and mro.index(ModernNetworkMixin) < mro.index(ModernSpiderFoot.__bases__[1]),
        "modern networking methods take precedence over legacy networking methods",
        "legacy networking may take precedence over modern networking",
    ))

    before_context: Callable = ssl._create_default_https_context
    core = None
    try:
        core = ModernSpiderFoot({"_dnsserver": ""})
        after_context: Callable = ssl._create_default_https_context
        checks.append(_result(
            "global TLS preservation",
            after_context is before_context,
            "constructing ModernSpiderFoot preserves Python's global HTTPS context",
            "constructing ModernSpiderFoot changed Python's global HTTPS context",
        ))
        checks.append(_result(
            "modern fetch binding",
            getattr(core.fetchUrl, "__func__", None) is ModernNetworkMixin.fetchUrl,
            "fetchUrl resolves to the modern compatibility implementation",
            "fetchUrl does not resolve to the modern compatibility implementation",
        ))
        checks.append(_result(
            "lazy HTTP client",
            core._modern_http_client is None,
            "HTTP client creation remains lazy until the first network request",
            "HTTP client was created during core construction",
        ))
    finally:
        if core is not None:
            core.close()

    return checks


def main() -> int:
    checks = verify_runtime()
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        print(f"[{status}] {check.name}: {check.detail}")

    failed = [check for check in checks if not check.ok]
    print(f"\nModern runtime checks: {len(checks) - len(failed)}/{len(checks)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

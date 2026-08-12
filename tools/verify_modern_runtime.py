#!/usr/bin/env python3
"""Verify MooSight's modern runtime routing and security invariants.

This check is intentionally local and network-free. It proves that the normal
MooSight entry point routes core, scanner, and web-UI construction through
modern compatibility facades and that constructing the core does not leave
process-wide HTTPS or DNS/socket behavior modified.
"""

from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass
from typing import Callable

import moosight
import sf
import sfscan
import sfwebui
from spiderfoot.modern_core import ModernSpiderFoot
from spiderfoot.modern_network_mixin import ModernNetworkMixin
from spiderfoot.modern_scanner import ModernSpiderFootScanner
from spiderfoot.modern_webui import ModernSpiderFootWebUi


_SOCKET_RESOLVER_FUNCTIONS = (
    "getaddrinfo",
    "getnameinfo",
    "getfqdn",
    "gethostbyname",
    "gethostbyname_ex",
    "gethostbyaddr",
)


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
        "sfscan.py core construction is routed to ModernSpiderFoot",
        "sfscan.py core construction is not routed to ModernSpiderFoot",
    ))
    checks.append(_result(
        "scanner facade routing",
        sfscan.SpiderFootScanner is ModernSpiderFootScanner,
        "scanner construction is routed to ModernSpiderFootScanner",
        "scanner construction is not routed to ModernSpiderFootScanner",
    ))
    checks.append(_result(
        "web UI facade routing",
        sf.SpiderFootWebUi is ModernSpiderFootWebUi,
        "web UI construction is routed to ModernSpiderFootWebUi",
        "web UI construction is not routed to ModernSpiderFootWebUi",
    ))
    checks.append(_result(
        "web UI core routing",
        sfwebui.SpiderFoot is ModernSpiderFoot,
        "sfwebui.py core construction is routed to ModernSpiderFoot",
        "sfwebui.py still constructs the legacy SpiderFoot core",
    ))

    mro = ModernSpiderFoot.__mro__
    checks.append(_result(
        "network method precedence",
        ModernNetworkMixin in mro and mro.index(ModernNetworkMixin) < mro.index(ModernSpiderFoot.__bases__[1]),
        "modern networking methods take precedence over legacy networking methods",
        "legacy networking may take precedence over modern networking",
    ))

    before_context: Callable = ssl._create_default_https_context
    before_socket_functions = {
        name: getattr(socket, name)
        for name in _SOCKET_RESOLVER_FUNCTIONS
        if hasattr(socket, name)
    }
    core = None
    try:
        core = ModernSpiderFoot({"_dnsserver": "1.1.1.1"})
        after_context: Callable = ssl._create_default_https_context
        checks.append(_result(
            "global TLS preservation",
            after_context is before_context,
            "constructing ModernSpiderFoot preserves Python's global HTTPS context",
            "constructing ModernSpiderFoot changed Python's global HTTPS context",
        ))

        resolver_preserved = all(
            getattr(socket, name) is function
            for name, function in before_socket_functions.items()
        )
        checks.append(_result(
            "global DNS resolver preservation",
            resolver_preserved,
            "constructing ModernSpiderFoot preserves process-wide socket resolver functions",
            "constructing ModernSpiderFoot changed process-wide socket resolver functions",
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

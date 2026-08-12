# -*- coding: utf-8 -*-
"""Modern scanner facade for MooSight.

This transitional subclass keeps the legacy scanner orchestration while making
scan-owned mutable collections instance-local. It also ensures the module list
passed by a caller cannot be mutated through scanner internals and prevents
scanner construction from permanently changing process-wide DNS resolution.
"""

from __future__ import annotations

import socket

from sfscan import SpiderFootScanner as LegacySpiderFootScanner


_SOCKET_RESOLVER_FUNCTIONS = (
    "getaddrinfo",
    "getnameinfo",
    "getfqdn",
    "gethostbyname",
    "gethostbyname_ex",
    "gethostbyaddr",
)


class ModernSpiderFootScanner(LegacySpiderFootScanner):
    """Legacy scanner behavior with isolated per-scan mutable state.

    The legacy scanner may ask dnspython to replace process-wide socket resolver
    functions when a custom DNS server is configured. MooSight restores the
    exact resolver functions present before construction so a scanner cannot
    leave the parent process globally modified after initialization completes.
    """

    def __init__(
        self,
        scanName: str,
        scanId: str,
        targetValue: str,
        targetType: str,
        moduleList: list,
        globalOpts: dict,
        start: bool = True,
    ) -> None:
        # These attributes are historically defined as mutable class values in
        # SpiderFootScanner. Assigning them here guarantees each scanner owns
        # independent collections even before legacy initialization touches them.
        self._SpiderFootScanner__moduleList = []
        self._SpiderFootScanner__moduleInstances = {}
        self._SpiderFootScanner__modconfig = {}

        # Pass an owned copy because the legacy initializer stores the list by
        # reference. This prevents scan setup from ever mutating caller state.
        owned_modules = list(moduleList) if isinstance(moduleList, list) else moduleList

        previous_socket_functions = {
            name: getattr(socket, name)
            for name in _SOCKET_RESOLVER_FUNCTIONS
            if hasattr(socket, name)
        }

        try:
            super().__init__(
                scanName,
                scanId,
                targetValue,
                targetType,
                owned_modules,
                globalOpts,
                start=start,
            )
        finally:
            # The legacy scanner calls dns.resolver.override_system_resolver().
            # Always restore the exact process resolver state after construction,
            # including when initialization raises.
            for name, function in previous_socket_functions.items():
                setattr(socket, name, function)

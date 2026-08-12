# -*- coding: utf-8 -*-
"""Modern scanner facade for MooSight.

This transitional subclass keeps the legacy scanner orchestration while making
scan-owned mutable collections instance-local. It also ensures the module list
passed by a caller cannot be mutated through scanner internals and prevents
custom DNS setup from remaining process-wide while a scan executes.
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
    functions when a custom DNS server is configured. MooSight forces legacy
    initialization to complete without starting the scan, restores the process
    resolver state, and only then starts scanning when requested. This keeps a
    custom scanner DNS setting from leaking across the entire application while
    the scan is running.
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
            # Always suppress legacy auto-start here. The old initializer changes
            # process-wide DNS resolver functions before reaching its start hook.
            # We restore those globals first and invoke the already-initialized
            # scanner afterward when the caller actually requested auto-start.
            super().__init__(
                scanName,
                scanId,
                targetValue,
                targetType,
                owned_modules,
                globalOpts,
                start=False,
            )
        finally:
            # The legacy scanner calls dns.resolver.override_system_resolver().
            # Always restore the exact process resolver state after construction,
            # including when initialization raises.
            for name, function in previous_socket_functions.items():
                setattr(socket, name, function)

        if start:
            self._SpiderFootScanner__startScan()

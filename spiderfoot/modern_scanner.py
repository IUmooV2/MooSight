# -*- coding: utf-8 -*-
"""Modern scanner facade for MooSight.

This transitional subclass keeps the legacy scanner orchestration while making
scan-owned mutable collections instance-local. It also ensures the module list
passed by a caller cannot be mutated through scanner internals and prevents
custom DNS setup from remaining process-wide while a scan executes.
"""

from __future__ import annotations

import socket
from copy import deepcopy

from sfscan import SpiderFootScanner as LegacySpiderFootScanner
from spiderfoot.config import NetworkConfig


_SOCKET_RESOLVER_FUNCTIONS = (
    "getaddrinfo",
    "getnameinfo",
    "getfqdn",
    "gethostbyname",
    "gethostbyname_ex",
    "gethostbyaddr",
)


class ModernSpiderFootScanner(LegacySpiderFootScanner):
    """Legacy scanner behavior with isolated per-scan mutable state."""

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
        self._SpiderFootScanner__moduleList = []
        self._SpiderFootScanner__moduleInstances = {}
        self._SpiderFootScanner__modconfig = {}

        owned_modules = list(moduleList) if isinstance(moduleList, list) else moduleList
        owned_options = deepcopy(globalOpts) if isinstance(globalOpts, dict) else globalOpts

        # Validate and normalize proxy settings before legacy scanner setup. This
        # makes the typed configuration the source of truth while retaining the
        # legacy scanner's expected dictionary interface during the transition.
        if isinstance(owned_options, dict):
            network_config = NetworkConfig.from_legacy(owned_options)
            if network_config.proxy_enabled:
                owned_options["_socks1type"] = network_config.proxy_type
                owned_options["_socks2addr"] = network_config.proxy_host
                owned_options["_socks3port"] = network_config.proxy_port
                owned_options["_socks4user"] = network_config.proxy_username
                owned_options["_socks5pwd"] = network_config.proxy_password
            else:
                # Keep legacy no-proxy behavior explicit and prevent stale proxy
                # fields from being interpreted independently downstream.
                owned_options["_socks1type"] = ""

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
                owned_options,
                start=False,
            )
        finally:
            for name, function in previous_socket_functions.items():
                setattr(socket, name, function)

        if start:
            self._SpiderFootScanner__startScan()

# -*- coding: utf-8 -*-
"""Modernized SpiderFoot core facade used during MooSight migration.

This class intentionally leaves the legacy ``sflib.SpiderFoot`` implementation
available while giving MooSight a drop-in core whose networking methods are
resolved from ``ModernNetworkMixin`` first. That lets us exercise the modern
transport stack before deleting the large legacy networking block from sflib.
"""

from __future__ import annotations

import socket
import ssl

from sflib import SpiderFoot as LegacySpiderFoot
from spiderfoot.modern_network_mixin import ModernNetworkMixin


_SOCKET_RESOLVER_FUNCTIONS = (
    "getaddrinfo",
    "getnameinfo",
    "getfqdn",
    "gethostbyname",
    "gethostbyname_ex",
    "gethostbyaddr",
)


class ModernSpiderFoot(ModernNetworkMixin, LegacySpiderFoot):
    """Legacy SpiderFoot behavior with MooSight's modern networking overrides.

    Method resolution order is deliberate: networking methods implemented by
    ``ModernNetworkMixin`` win over the historical implementations in
    ``LegacySpiderFoot``. All unrelated legacy behavior remains available.

    The legacy constructor currently changes process-wide TLS and DNS/socket
    behavior. Until that code is physically removed from ``sflib.py``, this
    facade contains those mutations to the constructor call and restores the
    exact process state immediately afterward.
    """

    def __init__(self, options: dict) -> None:
        previous_https_context = ssl._create_default_https_context
        previous_socket_functions = {
            name: getattr(socket, name)
            for name in _SOCKET_RESOLVER_FUNCTIONS
            if hasattr(socket, name)
        }

        try:
            super().__init__(options)
        finally:
            # LegacySpiderFoot currently assigns an unverified HTTPS context and
            # may ask dnspython to replace process-wide socket resolver helpers.
            # Never let either mutation escape construction of the modern core.
            ssl._create_default_https_context = previous_https_context
            for name, function in previous_socket_functions.items():
                setattr(socket, name, function)

        # Ensure network resources always start instance-local and lazy.
        self._modern_http_client = None
        self._modern_fetch_service = None

    def close(self) -> None:
        """Release resources owned by the modern core facade."""
        self.closeNetworkClient()

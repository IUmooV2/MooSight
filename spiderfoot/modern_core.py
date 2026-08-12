# -*- coding: utf-8 -*-
"""Modernized SpiderFoot core facade used during MooSight migration.

This class intentionally leaves the legacy ``sflib.SpiderFoot`` implementation
available while giving MooSight a drop-in core whose networking methods are
resolved from ``ModernNetworkMixin`` first. That lets us exercise the modern
transport stack before deleting the large legacy networking block from sflib.
"""

from __future__ import annotations

from sflib import SpiderFoot as LegacySpiderFoot
from spiderfoot.modern_network_mixin import ModernNetworkMixin


class ModernSpiderFoot(ModernNetworkMixin, LegacySpiderFoot):
    """Legacy SpiderFoot behavior with MooSight's modern networking overrides.

    Method resolution order is deliberate: networking methods implemented by
    ``ModernNetworkMixin`` win over the historical implementations in
    ``LegacySpiderFoot``. All unrelated legacy behavior remains available.
    """

    def __init__(self, options: dict) -> None:
        # Legacy initialization still configures database/logging-related state.
        # The global TLS mutation in LegacySpiderFoot remains a known migration
        # item until sflib itself is surgically cleaned up. Restore the previous
        # process-wide HTTPS context immediately so constructing this facade does
        # not leave the interpreter in an insecure state.
        import ssl

        previous_https_context = ssl._create_default_https_context
        try:
            super().__init__(options)
        finally:
            ssl._create_default_https_context = previous_https_context

        # Ensure network resources always start instance-local and lazy.
        self._modern_http_client = None
        self._modern_fetch_service = None

    def close(self) -> None:
        """Release resources owned by the modern core facade."""
        self.closeNetworkClient()

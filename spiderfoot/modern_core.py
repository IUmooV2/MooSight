# -*- coding: utf-8 -*-
"""Modernized SpiderFoot core facade used during MooSight migration.

The facade keeps the legacy ``sflib.SpiderFoot`` API surface available while
routing networking through MooSight's modern, instance-scoped implementation.
Its constructor intentionally initializes the small amount of safe legacy state
directly instead of calling the legacy constructor, which currently mutates
process-wide TLS and DNS resolver behavior.
"""

from __future__ import annotations

import logging
from copy import deepcopy

from sflib import SpiderFoot as LegacySpiderFoot
from spiderfoot.modern_network_mixin import ModernNetworkMixin


class ModernSpiderFoot(ModernNetworkMixin, LegacySpiderFoot):
    """Legacy SpiderFoot behavior with MooSight's modern networking overrides.

    Method resolution order is deliberate: networking methods implemented by
    ``ModernNetworkMixin`` win over the historical implementations in
    ``LegacySpiderFoot``. All unrelated legacy methods remain inherited.

    The legacy constructor only establishes the option copy/logger before
    applying global TLS/DNS mutations. MooSight reproduces the safe initialization
    locally and never invokes that side-effectful constructor.
    """

    def __init__(self, options: dict) -> None:
        if not isinstance(options, dict):
            raise TypeError(f"options is {type(options)}; expected dict()")

        # Match the safe state established by LegacySpiderFoot.__init__ without
        # its process-wide SSL or DNS resolver mutations.
        self.opts = deepcopy(options)
        self.log = logging.getLogger("spiderfoot.sflib")

        # Resource-owning modern networking components are created lazily.
        self._modern_http_client = None
        self._modern_fetch_service = None

    def close(self) -> None:
        """Release resources owned by the modern core facade."""
        self.closeNetworkClient()

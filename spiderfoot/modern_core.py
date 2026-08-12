# -*- coding: utf-8 -*-
"""Modernized SpiderFoot core facade used during MooSight migration.

This class intentionally leaves the legacy ``sflib.SpiderFoot`` implementation
available while giving MooSight a drop-in core whose networking methods are
resolved from ``ModernNetworkMixin`` first. That lets us exercise the modern
transport stack before deleting the large legacy networking block from sflib.
"""

from __future__ import annotations

import logging
from copy import deepcopy

from sflib import SpiderFoot as LegacySpiderFoot
from spiderfoot.modern_network_mixin import ModernNetworkMixin
from spiderfoot.security import redact_url


class ModernSpiderFoot(ModernNetworkMixin, LegacySpiderFoot):
    """Legacy SpiderFoot behavior with MooSight's modern networking overrides.

    Method resolution order is deliberate: networking methods implemented by
    ``ModernNetworkMixin`` win over the historical implementations in
    ``LegacySpiderFoot``. All unrelated legacy behavior remains available.

    The modern constructor does not invoke ``LegacySpiderFoot.__init__`` because
    the legacy constructor mutates process-wide TLS and DNS/socket behavior.
    Only the safe instance initialization needed by the rest of SpiderFoot is
    reproduced here.
    """

    def __init__(self, options: dict) -> None:
        if not isinstance(options, dict):
            raise TypeError(f"options is {type(options)}; expected dict()")

        self.opts = deepcopy(options)
        self.log = logging.getLogger("spiderfoot.sflib")
        self._modern_http_client = None
        self._modern_fetch_service = None

    def optValueToData(self, val: str) -> str | None:
        """Resolve an option value without bypassing the modern network stack.

        ``@path`` values are read as UTF-8 text and HTTP(S) values are fetched
        through :meth:`fetchUrl`, preserving configured proxy, timeout, TLS,
        retry, and redaction behavior. Plain strings are returned unchanged.
        """
        if not isinstance(val, str):
            self.error(f"Invalid option value {val}")
            return None

        if val.startswith("@"):
            path = val[1:]
            if not path:
                self.error("Invalid empty option file path")
                return None
            self.info(f"Loading configuration data from: {path}")
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    return handle.read()
            except (OSError, UnicodeError) as exc:
                self.error(f"Unable to open option file, {path}: {exc}")
                return None

        if val.lower().startswith(("http://", "https://")):
            self.info(f"Downloading configuration data from: {redact_url(val)}")
            result = self.fetchUrl(
                val,
                timeout=int(self.opts.get("_fetchtimeout", 5)),
                useragent=self.opts.get("_useragent", "SpiderFoot"),
                noLog=True,
                verify=True,
            )
            if not result or not result.get("content"):
                self.error(f"Unable to open option URL, {redact_url(val)}")
                return None

            content = result["content"]
            if isinstance(content, bytes):
                try:
                    return content.decode("utf-8")
                except UnicodeDecodeError as exc:
                    self.error(f"Unable to decode option URL, {redact_url(val)}: {exc}")
                    return None
            return str(content)

        return val

    def close(self) -> None:
        """Release resources owned by the modern core facade."""
        self.closeNetworkClient()

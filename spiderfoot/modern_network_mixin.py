# -*- coding: utf-8 -*-
"""Modern networking compatibility mixin for the legacy ``SpiderFoot`` core.

The goal of this mixin is to make the final ``sflib.SpiderFoot`` migration
small and reviewable. It exposes the historical method names used throughout
SpiderFoot while delegating the implementation to MooSight's validated,
instance-scoped networking components.

Nothing in this module mutates Python's global SSL context, DNS resolver, or
urllib3 warning filters.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

from spiderfoot.config import NetworkConfig
from spiderfoot.http_client import HttpClient
from spiderfoot.legacy_fetch import LegacyFetchService
from spiderfoot.security import redact_url
from spiderfoot.tls import create_tls_socket


class ModernNetworkMixin:
    """Provide legacy SpiderFoot networking method names using modern internals.

    A class using this mixin must expose ``opts`` as the traditional SpiderFoot
    options mapping. ``socksProxy`` is intentionally not used as the source of
    truth because proxy construction belongs to ``NetworkConfig``.
    """

    _modern_http_client: HttpClient | None = None
    _modern_fetch_service: LegacyFetchService | None = None

    def _network_config(self) -> NetworkConfig:
        """Return a validated typed view of the current legacy options."""
        return NetworkConfig.from_legacy(self.opts)

    def _http_client(self) -> HttpClient:
        """Lazily create one reusable HTTP client per SpiderFoot instance."""
        if self._modern_http_client is None:
            self._modern_http_client = HttpClient(self._network_config())
        return self._modern_http_client

    def _fetch_service(self) -> LegacyFetchService:
        """Lazily create the legacy compatibility service."""
        if self._modern_fetch_service is None:
            self._modern_fetch_service = LegacyFetchService(self._http_client())
        return self._modern_fetch_service

    def resetNetworkClient(self) -> None:
        """Discard pooled connections after network configuration changes.

        Legacy SpiderFoot can change proxy-related settings during startup. A
        reset gives those changes a deterministic lifecycle without mutating
        global Requests or socket state.
        """
        client = self._modern_http_client
        self._modern_fetch_service = None
        self._modern_http_client = None
        if client is not None:
            client.close()

    def closeNetworkClient(self) -> None:
        """Release pooled network resources owned by this instance."""
        self.resetNetworkClient()

    def getSession(self):
        """Return the instance-scoped Requests session.

        This keeps the historical method name for compatibility while avoiding
        a newly allocated session for every request.
        """
        return self._http_client().session

    def removeUrlCreds(self, url: str) -> str:
        """Return a logging-safe URL using the centralized redaction rules."""
        return redact_url(url)

    def safeSocket(self, host: str, port: int, timeout: int):
        """Create a bounded plain TCP socket without changing global state."""
        if not isinstance(host, str) or not host.strip():
            raise ValueError("host must be a non-empty string")
        try:
            port_value = int(port)
            timeout_value = float(timeout)
        except (TypeError, ValueError) as exc:
            raise ValueError("port and timeout must be numeric") from exc
        if not 1 <= port_value <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if timeout_value <= 0:
            raise ValueError("timeout must be greater than zero")

        sock = socket.create_connection((host.strip(), port_value), timeout_value)
        sock.settimeout(timeout_value)
        return sock

    def safeSSLSocket(
        self,
        host: str,
        port: int,
        timeout: int,
        *,
        verify: bool = True,
    ):
        """Create a scoped modern TLS socket.

        ``verify`` defaults to True. Certificate-analysis modules that need to
        inspect a broken/untrusted endpoint can explicitly pass ``False``.
        """
        return create_tls_socket(host, port, timeout, verify=verify)

    def useProxyForUrl(self, url: str) -> bool:
        """Return whether the configured proxy should handle a URL.

        The decision is based on validated ``NetworkConfig`` rather than direct
        magic-key lookups. Loopback, private, link-local and local hostnames are
        kept off the proxy, as is the proxy server itself.
        """
        config = self._network_config()
        if not config.proxy_enabled:
            return False
        if not isinstance(url, str) or not url.strip():
            return False

        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False

        host = parsed.hostname.rstrip(".").lower()
        if host == config.proxy_host.rstrip(".").lower():
            return False
        if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
            return False

        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return True

        if address.is_private or address.is_loopback or address.is_link_local:
            return False
        return True

    def fetchUrl(
        self,
        url: str,
        cookies: Any = None,
        timeout: int = 30,
        useragent: str = "SpiderFoot",
        headers: dict | None = None,
        noLog: bool = False,
        postData: Any = None,
        disableContentEncoding: bool = False,
        sizeLimit: int | None = None,
        headOnly: bool = False,
        verify: bool = True,
    ) -> dict | None:
        """Compatibility wrapper for the historical ``SpiderFoot.fetchUrl`` API.

        The return structure remains legacy-compatible while transport,
        retries, TLS handling, proxy configuration, response classification,
        and secret redaction are delegated to the modern network stack.
        """
        if not url:
            return None

        try:
            result = self._fetch_service().fetch(
                url,
                cookies=cookies,
                timeout=timeout,
                useragent=useragent,
                headers=headers,
                post_data=postData,
                disable_content_encoding=disableContentEncoding,
                size_limit=sizeLimit,
                head_only=headOnly,
                verify=verify,
            )
        except (TypeError, ValueError) as exc:
            # Preserve SpiderFoot's historical invalid-input behavior rather
            # than allowing a malformed target to terminate the scan.
            debug = getattr(self, "debug", None)
            if callable(debug):
                debug(f"Unable to fetch invalid URL {redact_url(url)}: {exc}")
            return None

        # ``noLog`` historically changed verbosity rather than request
        # semantics. Keep diagnostics small and secret-safe.
        message = (
            f"Fetched {redact_url(url)} "
            f"(HTTP {result.get('code') or 'n/a'}, "
            f"{len(result.get('content') or b'')} bytes)"
        )
        logger = getattr(self, "debug" if noLog else "info", None)
        if callable(logger):
            logger(message)

        return result

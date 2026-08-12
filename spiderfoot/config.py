# -*- coding: utf-8 -*-
"""Typed configuration helpers for MooSight modernization.

Legacy SpiderFoot configuration is dictionary-based and remains supported. This
module provides validated typed views over high-risk settings so new code can
avoid scattering magic-key lookups throughout the codebase.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Any
from urllib.parse import quote


_PROXY_DEFAULT_PORTS = {
    "4": 1080,
    "5": 1080,
    "HTTP": 8080,
    "TOR": 9050,
}


@dataclass(frozen=True)
class NetworkConfig:
    """Validated network settings derived from the legacy configuration dict."""

    timeout: int = 5
    user_agent: str = "SpiderFoot"
    dns_server: str = ""
    proxy_type: str = ""
    proxy_host: str = ""
    proxy_port: int | None = None
    proxy_username: str = ""
    proxy_password: str = ""

    @classmethod
    def from_legacy(cls, options: Mapping[str, Any]) -> "NetworkConfig":
        if not isinstance(options, Mapping):
            raise TypeError("options must be a mapping")

        timeout = options.get("_fetchtimeout", 5)
        try:
            timeout = int(timeout)
        except (TypeError, ValueError) as exc:
            raise ValueError("_fetchtimeout must be an integer") from exc
        if timeout <= 0:
            raise ValueError("_fetchtimeout must be greater than zero")

        proxy_type = str(options.get("_socks1type", "") or "").upper().strip()
        if proxy_type and proxy_type not in _PROXY_DEFAULT_PORTS:
            raise ValueError("_socks1type must be one of: 4, 5, HTTP, TOR")

        proxy_host = str(options.get("_socks2addr", "") or "").strip()
        if proxy_type and not proxy_host:
            raise ValueError("_socks2addr is required when a proxy type is configured")

        raw_port = options.get("_socks3port", "")
        proxy_port = None
        if raw_port not in (None, ""):
            try:
                proxy_port = int(raw_port)
            except (TypeError, ValueError) as exc:
                raise ValueError("_socks3port must be an integer") from exc
            if not 1 <= proxy_port <= 65535:
                raise ValueError("_socks3port must be between 1 and 65535")
        elif proxy_type:
            # Match SpiderFoot's historical defaults while keeping the decision
            # centralized and testable in the typed configuration layer.
            proxy_port = _PROXY_DEFAULT_PORTS[proxy_type]

        proxy_username = str(options.get("_socks4user", "") or "")
        proxy_password = str(options.get("_socks5pwd", "") or "")
        if proxy_password and not proxy_username:
            raise ValueError("_socks4user is required when _socks5pwd is configured")

        return cls(
            timeout=timeout,
            user_agent=str(options.get("_useragent", "SpiderFoot") or "SpiderFoot"),
            dns_server=str(options.get("_dnsserver", "") or "").strip(),
            proxy_type=proxy_type,
            proxy_host=proxy_host,
            proxy_port=proxy_port,
            proxy_username=proxy_username,
            proxy_password=proxy_password,
        )

    @property
    def proxy_enabled(self) -> bool:
        return bool(self.proxy_type and self.proxy_host and self.proxy_port)

    def proxy_url(self) -> str | None:
        """Return a requests-compatible proxy URL, or None when disabled."""
        if not self.proxy_enabled:
            return None

        scheme = {
            "4": "socks4",
            "5": "socks5",
            "TOR": "socks5h",
            "HTTP": "http",
        }[self.proxy_type]

        auth = ""
        if self.proxy_username:
            username = quote(self.proxy_username, safe="")
            if self.proxy_password:
                password = quote(self.proxy_password, safe="")
                auth = f"{username}:{password}@"
            else:
                auth = f"{username}@"

        return f"{scheme}://{auth}{self.proxy_host}:{self.proxy_port}"


@dataclass(frozen=True)
class RuntimeConfig:
    """Small validated view of core runtime settings."""

    debug: bool = False
    logging_enabled: bool = True
    max_threads: int = 3
    network: NetworkConfig = NetworkConfig()

    @classmethod
    def from_legacy(cls, options: Mapping[str, Any]) -> "RuntimeConfig":
        if not isinstance(options, Mapping):
            raise TypeError("options must be a mapping")

        try:
            max_threads = int(options.get("_maxthreads", 3))
        except (TypeError, ValueError) as exc:
            raise ValueError("_maxthreads must be an integer") from exc
        if max_threads <= 0:
            raise ValueError("_maxthreads must be greater than zero")

        return cls(
            debug=bool(options.get("_debug", False)),
            logging_enabled=bool(options.get("__logging", True)),
            max_threads=max_threads,
            network=NetworkConfig.from_legacy(options),
        )

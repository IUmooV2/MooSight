# -*- coding: utf-8 -*-
"""Reusable HTTP client facade for MooSight.

This layer composes validated configuration, isolated sessions, normalized
network results, and legacy compatibility output. It is designed to become the
single integration point for legacy SpiderFoot fetch behavior without forcing
hundreds of modules to change at once.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Any

from spiderfoot.config import NetworkConfig
from spiderfoot.network import NetworkResult, build_session, build_session_from_config, request_with_config
from spiderfoot.network_legacy import to_legacy_result


@dataclass
class HttpClient:
    """Small stateful client built around one validated network configuration."""

    config: NetworkConfig

    def __post_init__(self) -> None:
        if not isinstance(self.config, NetworkConfig):
            raise TypeError("config must be a NetworkConfig")
        self._session = build_session_from_config(self.config)

    @classmethod
    def from_legacy(cls, options: Mapping[str, Any]) -> "HttpClient":
        """Build a client directly from the legacy SpiderFoot option mapping."""
        return cls(NetworkConfig.from_legacy(options))

    @property
    def session(self):
        """Expose the isolated requests session for diagnostics/testing."""
        return self._session

    def request(
        self,
        method: str,
        url: str,
        *,
        timeout: float | tuple[float, float] | None = None,
        verify: bool = True,
        headers: Mapping[str, str] | None = None,
        cookies=None,
        data=None,
        allow_redirects: bool = True,
        size_limit: int | None = None,
    ) -> NetworkResult:
        """Perform one normalized request using this client's isolated session.

        When a proxy is configured, local/private targets deliberately use a
        short-lived direct session. This preserves SpiderFoot's historical proxy
        bypass behavior without mutating the reusable proxied session.
        """
        direct_session = None
        active_session = self._session
        if self.config.proxy_enabled and not self.config.should_proxy_url(url):
            direct_session = build_session()
            active_session = direct_session

        try:
            return request_with_config(
                self.config,
                method,
                url,
                session=active_session,
                timeout=timeout,
                verify=verify,
                headers=headers,
                cookies=cookies,
                data=data,
                allow_redirects=allow_redirects,
                size_limit=size_limit,
            )
        finally:
            if direct_session is not None:
                direct_session.close()

    def get(self, url: str, **kwargs) -> NetworkResult:
        return self.request("GET", url, **kwargs)

    def head(self, url: str, **kwargs) -> NetworkResult:
        return self.request("HEAD", url, **kwargs)

    def post(self, url: str, *, data=None, **kwargs) -> NetworkResult:
        return self.request("POST", url, data=data, **kwargs)

    def request_legacy(
        self,
        method: str,
        url: str,
        *,
        disable_content_encoding: bool = False,
        **kwargs,
    ) -> dict:
        """Return the historical ``fetchUrl``-style dictionary shape.

        This is the compatibility seam intended for gradual ``sflib.py``
        migration. The normalized NetworkResult remains the source of truth.
        """
        result = self.request(method, url, **kwargs)
        return to_legacy_result(
            result,
            requested_url=url,
            disable_content_encoding=disable_content_encoding,
        )

    def close(self) -> None:
        """Release pooled HTTP connections owned by this client."""
        self._session.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

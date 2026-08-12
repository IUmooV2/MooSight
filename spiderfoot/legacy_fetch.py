# -*- coding: utf-8 -*-
"""Compatibility service for legacy SpiderFoot ``fetchUrl`` behavior.

This module preserves the historical dictionary-shaped return contract while
moving request execution onto MooSight's typed ``HttpClient``. It deliberately
contains no global TLS or warning mutations.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Mapping, Any
from urllib.parse import urljoin, urlparse

from spiderfoot.http_client import HttpClient
from spiderfoot.network_legacy import to_legacy_result
from spiderfoot.security import redact_cookies, redact_headers, redact_proxy, redact_url


@dataclass
class LegacyFetchService:
    """Bridge old ``fetchUrl`` call semantics to the modern HTTP client."""

    client: HttpClient

    def __post_init__(self) -> None:
        if not isinstance(self.client, HttpClient):
            raise TypeError("client must be an HttpClient")

    @classmethod
    def from_legacy(cls, options: Mapping[str, Any]) -> "LegacyFetchService":
        return cls(HttpClient.from_legacy(options))

    @staticmethod
    def _validate_url(url: str) -> str:
        if not isinstance(url, str) or not url.strip():
            raise ValueError("url must be a non-empty string")
        value = url.strip()
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must use http or https and include a host")
        return value

    @staticmethod
    def _headers(useragent: str | list[str], headers: Mapping[str, Any] | None) -> dict[str, str]:
        if isinstance(useragent, list):
            choices = [str(item) for item in useragent if str(item)]
            if not choices:
                raise ValueError("useragent list must contain at least one value")
            selected = random.SystemRandom().choice(choices)
        else:
            selected = str(useragent)

        merged = {"User-Agent": selected}
        if headers:
            merged.update({str(key): str(value) for key, value in headers.items()})
        return merged

    def diagnostic_metadata(
        self,
        *,
        url: str,
        timeout: int | float,
        headers: Mapping[str, str],
        cookies=None,
    ) -> dict[str, str]:
        """Return safe request metadata suitable for logging."""
        return {
            "url": redact_url(url),
            "proxy": redact_proxy(self.client.config.proxy_url()),
            "timeout": str(timeout),
            "headers": str(redact_headers(headers)),
            "cookies": redact_cookies(cookies),
        }

    def fetch(
        self,
        url: str,
        *,
        cookies=None,
        timeout: int | float | None = None,
        useragent: str | list[str] = "SpiderFoot",
        headers: Mapping[str, Any] | None = None,
        post_data=None,
        disable_content_encoding: bool = False,
        size_limit: int | None = None,
        head_only: bool = False,
        verify: bool = True,
        max_refresh_redirects: int = 3,
    ) -> dict:
        """Perform a legacy-style fetch using the modern network stack.

        ``HEAD`` is performed first when ``head_only`` or ``size_limit`` is
        requested. A server-provided HTTP Refresh header is followed with a
        bounded recursion limit so malformed services cannot loop forever.
        """
        url = self._validate_url(url)
        if size_limit is not None and size_limit < 0:
            raise ValueError("size_limit must be non-negative")
        if max_refresh_redirects < 0:
            raise ValueError("max_refresh_redirects must be non-negative")

        timeout = self.client.config.timeout if timeout is None else timeout
        request_headers = self._headers(useragent, headers)

        if head_only or size_limit is not None:
            head_result = self.client.head(
                url,
                timeout=timeout,
                verify=verify,
                headers=request_headers,
                allow_redirects=True,
            )
            legacy_head = to_legacy_result(head_result, requested_url=url)

            if head_only:
                return legacy_head

            content_length = head_result.headers.get("content-length")
            if content_length:
                try:
                    if int(content_length) > size_limit:
                        return legacy_head
                except (TypeError, ValueError):
                    # Invalid Content-Length is not definitive; continue with
                    # the bounded GET and enforce the actual response size.
                    pass

        method = "POST" if post_data is not None else "GET"
        result = self.client.request(
            method,
            url,
            timeout=timeout,
            verify=verify,
            headers=request_headers,
            cookies=cookies,
            data=post_data,
            allow_redirects=True,
            size_limit=size_limit,
        )
        legacy = to_legacy_result(
            result,
            requested_url=url,
            disable_content_encoding=disable_content_encoding,
        )

        refresh = result.headers.get("refresh") if result.headers else None
        if not refresh or max_refresh_redirects == 0:
            return legacy

        # Refresh syntax varies in the wild. Handle the common
        # ``seconds;url=...`` form case-insensitively and resolve relatives.
        parts = refresh.split(";", 1)
        if len(parts) != 2 or "=" not in parts[1]:
            return legacy
        key, target = parts[1].split("=", 1)
        if key.strip().lower() != "url":
            return legacy
        target = target.strip().strip('"').strip("'")
        if not target:
            return legacy

        refresh_url = urljoin(result.url or url, target)
        return self.fetch(
            refresh_url,
            cookies=cookies,
            timeout=timeout,
            useragent=useragent,
            headers=headers,
            post_data=post_data,
            disable_content_encoding=disable_content_encoding,
            size_limit=size_limit,
            head_only=head_only,
            verify=verify,
            max_refresh_redirects=max_refresh_redirects - 1,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "LegacyFetchService":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

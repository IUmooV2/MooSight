# -*- coding: utf-8 -*-
"""Core networking primitives for MooSight.

This module is intentionally small and side-effect free. It provides a typed
result model, an isolated session factory, and narrowly scoped request/TLS
behavior that can be adopted incrementally by legacy SpiderFoot networking
code.
"""

from __future__ import annotations

import warnings
from contextlib import nullcontext
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Sequence

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from spiderfoot.config import NetworkConfig
from spiderfoot.security import redact_url


class NetworkState(str, Enum):
    """Normalized outcome for a network operation."""

    SUCCESS = "success"
    NOT_FOUND = "not_found"
    AUTH_REQUIRED = "auth_required"
    RATE_LIMITED = "rate_limited"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    TLS_ERROR = "tls_error"
    NETWORK_ERROR = "network_error"
    INVALID_RESPONSE = "invalid_response"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class NetworkResult:
    """Normalized result returned by MooSight network adapters."""

    state: NetworkState
    status_code: Optional[int] = None
    url: Optional[str] = None
    content: bytes | str | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    error: Optional[str] = None
    tls_verified: bool = True

    @property
    def ok(self) -> bool:
        return self.state == NetworkState.SUCCESS


class ScopedInsecureRequestWarnings:
    """Temporarily suppress only urllib3's insecure-request warning.

    This is for explicit requests using ``verify=False``. It does not alter
    Python's global SSL context and warning suppression ends when the context
    exits.
    """

    def __enter__(self):
        self._catcher = warnings.catch_warnings()
        self._catcher.__enter__()
        warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self._catcher.__exit__(exc_type, exc_value, traceback)


def build_session(
    proxy_url: str | None = None,
    *,
    retries: int = 2,
    backoff_factor: float = 0.25,
    retry_statuses: Sequence[int] = (429, 500, 502, 503, 504),
) -> requests.Session:
    """Create an isolated Requests session with a conservative retry policy.

    Retries are bounded and use urllib3's default idempotent-method policy, so
    ordinary POST requests are not retried automatically. ``Retry-After`` is
    respected when a remote service supplies it.
    """
    if not isinstance(retries, int) or retries < 0:
        raise ValueError("retries must be a non-negative integer")
    if backoff_factor < 0:
        raise ValueError("backoff_factor must be non-negative")

    retry_policy = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=backoff_factor,
        status_forcelist=tuple(retry_statuses),
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry_policy)

    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    if proxy_url:
        session.proxies.update({
            "http": proxy_url,
            "https": proxy_url,
        })
    return session


def build_session_from_config(
    config: NetworkConfig,
    *,
    retries: int = 2,
    backoff_factor: float = 0.25,
    retry_statuses: Sequence[int] = (429, 500, 502, 503, 504),
) -> requests.Session:
    """Create an isolated session directly from validated network settings."""
    if not isinstance(config, NetworkConfig):
        raise TypeError("config must be a NetworkConfig")
    return build_session(
        config.proxy_url(),
        retries=retries,
        backoff_factor=backoff_factor,
        retry_statuses=retry_statuses,
    )


def classify_http_status(status_code: int | None) -> NetworkState:
    """Map an HTTP status code to a conservative network state."""
    if status_code is None:
        return NetworkState.INDETERMINATE
    if 200 <= status_code < 400:
        return NetworkState.SUCCESS
    if status_code in (401, 407):
        return NetworkState.AUTH_REQUIRED
    if status_code == 403:
        return NetworkState.BLOCKED
    if status_code == 404:
        return NetworkState.NOT_FOUND
    if status_code == 429:
        return NetworkState.RATE_LIMITED
    if 400 <= status_code < 600:
        return NetworkState.INVALID_RESPONSE
    return NetworkState.INDETERMINATE


def classify_exception(exc: BaseException) -> NetworkState:
    """Map common Requests exceptions without hiding unexpected failures."""
    if isinstance(exc, requests.exceptions.SSLError):
        return NetworkState.TLS_ERROR
    if isinstance(exc, requests.exceptions.Timeout):
        return NetworkState.TIMEOUT
    if isinstance(exc, requests.exceptions.ConnectionError):
        return NetworkState.NETWORK_ERROR
    if isinstance(exc, requests.exceptions.RequestException):
        return NetworkState.NETWORK_ERROR
    return NetworkState.INDETERMINATE


def request_url(
    session: requests.Session,
    method: str,
    url: str,
    *,
    timeout: float | tuple[float, float] = 30,
    verify: bool = True,
    headers: Mapping[str, str] | None = None,
    cookies=None,
    data=None,
    allow_redirects: bool = True,
    size_limit: int | None = None,
) -> NetworkResult:
    """Perform one HTTP request without altering process-wide TLS behavior.

    This adapter intentionally returns a normalized result instead of raising
    routine network exceptions. Unexpected programming errors are represented
    as ``INDETERMINATE`` with a sanitized URL so callers can distinguish them
    from a definitive negative finding.
    """
    if not isinstance(session, requests.Session):
        raise TypeError("session must be a requests.Session")
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")

    method = str(method).upper().strip()
    if method not in {"GET", "HEAD", "POST"}:
        raise ValueError(f"unsupported HTTP method: {method}")
    if size_limit is not None and size_limit < 0:
        raise ValueError("size_limit must be non-negative")

    safe_url = redact_url(url.strip())
    warning_context = nullcontext() if verify else ScopedInsecureRequestWarnings()

    try:
        with warning_context:
            response = session.request(
                method,
                url.strip(),
                timeout=timeout,
                verify=verify,
                headers=dict(headers or {}),
                cookies=cookies,
                data=data,
                allow_redirects=allow_redirects,
            )
    except requests.exceptions.RequestException as exc:
        return NetworkResult(
            state=classify_exception(exc),
            url=safe_url,
            error=str(exc),
            tls_verified=verify,
        )
    except Exception as exc:
        return NetworkResult(
            state=NetworkState.INDETERMINATE,
            url=safe_url,
            error=f"{type(exc).__name__}: {exc}",
            tls_verified=verify,
        )

    headers_out = {str(k).lower(): str(v) for k, v in response.headers.items()}
    content = response.content
    state = classify_http_status(response.status_code)

    if size_limit is not None and len(content) > size_limit:
        content = None
        state = NetworkState.INVALID_RESPONSE

    return NetworkResult(
        state=state,
        status_code=response.status_code,
        url=redact_url(response.url or url),
        content=content,
        headers=headers_out,
        tls_verified=verify,
    )


def request_with_config(
    config: NetworkConfig,
    method: str,
    url: str,
    *,
    session: requests.Session | None = None,
    timeout: float | tuple[float, float] | None = None,
    verify: bool = True,
    headers: Mapping[str, str] | None = None,
    cookies=None,
    data=None,
    allow_redirects: bool = True,
    size_limit: int | None = None,
) -> NetworkResult:
    """Perform a request using validated network defaults.

    A caller may supply an existing session to retain connection pooling across
    requests. When omitted, a correctly configured isolated session is created.
    A per-request timeout overrides the configured default when supplied.
    """
    if not isinstance(config, NetworkConfig):
        raise TypeError("config must be a NetworkConfig")

    request_headers = {str(k): str(v) for k, v in (headers or {}).items()}
    if not any(key.lower() == "user-agent" for key in request_headers):
        request_headers["User-Agent"] = config.user_agent

    active_session = session or build_session_from_config(config)
    effective_timeout = config.timeout if timeout is None else timeout
    return request_url(
        active_session,
        method,
        url,
        timeout=effective_timeout,
        verify=verify,
        headers=request_headers,
        cookies=cookies,
        data=data,
        allow_redirects=allow_redirects,
        size_limit=size_limit,
    )

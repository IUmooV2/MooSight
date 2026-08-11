# -*- coding: utf-8 -*-
"""Core networking primitives for MooSight.

This module is intentionally small and side-effect free. It provides a typed
result model, a session factory, and a narrowly scoped TLS-warning context that
can be adopted incrementally by legacy SpiderFoot networking code.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional

import requests
import urllib3


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
    """Normalized result returned by future MooSight network adapters."""

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


def build_session(proxy_url: str | None = None) -> requests.Session:
    """Create an isolated Requests session without changing global state."""
    session = requests.Session()
    if proxy_url:
        session.proxies.update({
            "http": proxy_url,
            "https": proxy_url,
        })
    return session


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

# -*- coding: utf-8 -*-
"""Security helpers for safe diagnostic logging.

These functions are intentionally dependency-free so they can be used by the
core networking, scanner, web, and module layers without introducing import
cycles or additional runtime dependencies.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_REDACTED = "[REDACTED]"

_SENSITIVE_NAMES = {
    "access_token",
    "api-key",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "cookie",
    "key",
    "password",
    "passwd",
    "pass",
    "proxy-authorization",
    "secret",
    "session",
    "sessionid",
    "token",
}


_BEARER_RE = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+")
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)(?P<name>access_token|api[-_]?key|apikey|authorization|cookie|password|passwd|pass|secret|sessionid|token)"
    r"(?P<separator>\s*[:=]\s*)"
    r"(?P<value>[^\s,;&\)\]]+)"
)
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_PROXY_RE = re.compile(r"(?i)\b(?:socks4a?|socks5h?|https?)://[^\s,\)]+")


def is_sensitive_name(name: Any) -> bool:
    """Return True when a key/header/parameter name should be redacted."""
    if name is None:
        return False
    normalized = str(name).strip().lower()
    return normalized in _SENSITIVE_NAMES or any(
        marker in normalized
        for marker in ("token", "secret", "password", "passwd", "api_key", "apikey")
    )


def redact_headers(headers: Mapping | None) -> dict:
    """Return a copy of headers with credential-bearing values redacted."""
    if not headers:
        return {}

    redacted = {}
    for key, value in headers.items():
        redacted[str(key)] = _REDACTED if is_sensitive_name(key) else value
    return redacted


def redact_cookies(cookies: Any) -> str:
    """Return a safe representation of cookies without exposing values."""
    if not cookies:
        return "None"

    if isinstance(cookies, Mapping):
        names = sorted(str(name) for name in cookies.keys())
        return "{" + ", ".join(f"{name}={_REDACTED}" for name in names) + "}"

    parts = []
    for segment in str(cookies).split(";"):
        segment = segment.strip()
        if not segment:
            continue
        name = segment.split("=", 1)[0].strip()
        if name:
            parts.append(f"{name}={_REDACTED}")
    return "; ".join(parts) if parts else _REDACTED


def _safe_endpoint(parsed) -> tuple[str, str] | None:
    """Return a safe scheme/host endpoint or None for malformed netloc data."""
    try:
        hostname = parsed.hostname
        port = parsed.port
    except (ValueError, UnicodeError):
        return None

    if not parsed.scheme or not hostname:
        return None

    host = hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if port is not None:
        host = f"{host}:{port}"
    return parsed.scheme, host


def redact_proxy(proxy_url: Any) -> str:
    """Remove user information from a proxy URL while retaining endpoint data.

    Malformed proxy URLs fail closed. Redaction code is commonly executed while
    handling another error and must never raise or echo potentially sensitive
    malformed input back into logs.
    """
    if not proxy_url:
        return "None"

    try:
        parsed = urlsplit(str(proxy_url))
        endpoint = _safe_endpoint(parsed)
    except (ValueError, UnicodeError):
        return _REDACTED

    if endpoint is None:
        return _REDACTED

    scheme, host = endpoint
    try:
        has_credentials = parsed.username is not None or parsed.password is not None
    except (ValueError, UnicodeError):
        return _REDACTED

    if has_credentials:
        host = f"{_REDACTED}@{host}"

    return urlunsplit((scheme, host, parsed.path, parsed.query, parsed.fragment))


def redact_url(url: Any) -> str:
    """Redact URL userinfo and sensitive query parameters without raising."""
    if not url:
        return str(url)

    value = str(url)
    try:
        parsed = urlsplit(value)
        endpoint = _safe_endpoint(parsed) if parsed.netloc else None
    except (ValueError, UnicodeError):
        return _REDACTED

    netloc = parsed.netloc
    if parsed.netloc:
        if endpoint is None:
            return _REDACTED
        _, host = endpoint
        try:
            has_credentials = parsed.username is not None or parsed.password is not None
        except (ValueError, UnicodeError):
            return _REDACTED
        netloc = f"{_REDACTED}@{host}" if has_credentials else host

    try:
        query = []
        for key, val in parse_qsl(parsed.query, keep_blank_values=True):
            query.append((key, _REDACTED if is_sensitive_name(key) else val))
        safe = urlunsplit((parsed.scheme, netloc, parsed.path, urlencode(query, doseq=True), parsed.fragment))
    except (ValueError, UnicodeError):
        return _REDACTED

    return _BEARER_RE.sub(lambda m: f"{m.group(1)} {_REDACTED}", safe)


def redact_mapping(values: Mapping | None) -> dict:
    """Return a shallow redacted copy of configuration/request metadata."""
    if not values:
        return {}

    result = {}
    for key, value in values.items():
        result[key] = _REDACTED if is_sensitive_name(key) else value
    return result


def redact_text(message: Any) -> str:
    """Return a defensively redacted representation of arbitrary log text."""
    if message is None:
        return "None"

    text = str(message)
    text = _BEARER_RE.sub(lambda m: f"{m.group(1)} {_REDACTED}", text)
    text = _URL_RE.sub(lambda m: redact_url(m.group(0)), text)
    text = _PROXY_RE.sub(lambda m: redact_proxy(m.group(0)), text)
    text = _SENSITIVE_ASSIGNMENT_RE.sub(
        lambda m: f"{m.group('name')}{m.group('separator')}{_REDACTED}",
        text,
    )
    return text

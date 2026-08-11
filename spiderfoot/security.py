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

# Names commonly used for credentials or sensitive session material in URLs,
# headers, settings, and request metadata. Matching is case-insensitive.
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

    # Cookie strings can contain arbitrary service-specific values. Preserve
    # names only when they are straightforward name=value pairs.
    parts = []
    for segment in str(cookies).split(";"):
        segment = segment.strip()
        if not segment:
            continue
        name = segment.split("=", 1)[0].strip()
        if name:
            parts.append(f"{name}={_REDACTED}")
    return "; ".join(parts) if parts else _REDACTED


def redact_proxy(proxy_url: Any) -> str:
    """Remove user information from a proxy URL while retaining endpoint data."""
    if not proxy_url:
        return "None"

    value = str(proxy_url)
    try:
        parsed = urlsplit(value)
    except ValueError:
        return _REDACTED

    if not parsed.scheme or not parsed.hostname:
        return _REDACTED

    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parsed.port:
        host = f"{host}:{parsed.port}"

    # If credentials were present, signal that fact without reproducing them.
    if parsed.username is not None or parsed.password is not None:
        host = f"{_REDACTED}@{host}"

    return urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))


def redact_url(url: Any) -> str:
    """Redact URL userinfo and sensitive query parameters.

    The function is conservative: malformed URLs are passed through a final
    bearer/basic-token scrub rather than raising from logging code.
    """
    if not url:
        return str(url)

    value = str(url)
    try:
        parsed = urlsplit(value)
    except ValueError:
        return _BEARER_RE.sub(lambda m: f"{m.group(1)} {_REDACTED}", value)

    netloc = parsed.netloc
    if parsed.hostname:
        host = parsed.hostname
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        if parsed.port:
            host = f"{host}:{parsed.port}"
        if parsed.username is not None or parsed.password is not None:
            netloc = f"{_REDACTED}@{host}"
        else:
            netloc = host

    query = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=True):
        query.append((key, _REDACTED if is_sensitive_name(key) else val))

    safe = urlunsplit((parsed.scheme, netloc, parsed.path, urlencode(query, doseq=True), parsed.fragment))
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
    """Return a defensively redacted representation of arbitrary log text.

    This is a final safety net for messages emitted by legacy modules that may
    interpolate credentials directly. New code should still redact structured
    values before formatting them into a log message.
    """
    if message is None:
        return "None"

    text = str(message)
    text = _BEARER_RE.sub(lambda m: f"{m.group(1)} {_REDACTED}", text)

    # Scrub complete URLs first so query parameters and URL userinfo are handled
    # using URL-aware parsing rather than only regular expressions.
    text = _URL_RE.sub(lambda m: redact_url(m.group(0)), text)

    # Proxy URLs may use SOCKS schemes, which are outside _URL_RE.
    text = _PROXY_RE.sub(lambda m: redact_proxy(m.group(0)), text)

    # Catch key=value or Header: value strings from legacy modules. This runs
    # after URL processing so it does not interfere with URL reconstruction.
    text = _SENSITIVE_ASSIGNMENT_RE.sub(
        lambda m: f"{m.group('name')}{m.group('separator')}{_REDACTED}",
        text,
    )
    return text

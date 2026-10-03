# -*- coding: utf-8 -*-
"""Friendly scan-target normalization for MooSight's web UI."""

from __future__ import annotations

import re
from urllib.parse import urlparse


_USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")


def _quote_username(value: str) -> str | None:
    value = value.strip().lstrip("@").strip()
    if _USERNAME_RE.fullmatch(value):
        return f'"{value}"'
    return None


def _username_from_profile_url(value: str) -> str | None:
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"}:
        return None

    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    parts = [part for part in parsed.path.split("/") if part]
    username = None

    if (
        host == "instagram.com"
        and len(parts) == 1
        and parts[0].lower() not in {"accounts", "explore", "p", "reel", "stories"}
    ) or (host in {"x.com", "twitter.com", "github.com", "twitch.tv", "paypal.me"} and len(parts) == 1):
        username = parts[0]
    elif (
        host in {"tiktok.com", "threads.net", "threads.com"}
        and len(parts) == 1
        and parts[0].startswith("@")
    ):
        username = parts[0][1:]
    elif (
        (host == "reddit.com" and len(parts) == 2 and parts[0].lower() in {"u", "user"})
        or (host == "bsky.app" and len(parts) == 2 and parts[0].lower() == "profile")
        or (host in {"venmo.com", "account.venmo.com"} and len(parts) == 2 and parts[0].lower() == "u")
    ):
        username = parts[1]

    return _quote_username(username) if username else None


def normalize_scan_target(value: str, *, recognized_type: str | None = None) -> str:
    """Normalize user-friendly username forms while preserving known targets.

    Existing quoted targets and targets already recognized by SpiderFoot remain
    unchanged. Explicit ``@username`` and supported profile URLs are always
    normalized. Bare username tokens are normalized when SpiderFoot cannot
    recognize them as another target type, including numeric final labels that
    the legacy parser misclassifies as internet names.

    Args:
        value: The target entered by the user.
        recognized_type: The target type returned by SpiderFoot's legacy parser.

    Returns:
        A scan target in a format accepted by SpiderFoot.
    """
    if not isinstance(value, str):
        return value
    value = value.strip()
    if not value:
        return value
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value

    if value.startswith("@"):
        return _quote_username(value) or value

    profile_username = _username_from_profile_url(value)
    if profile_username:
        return profile_username

    # SpiderFoot's legacy target parser accepts numeric final labels as
    # INTERNET_NAME values, but social usernames commonly end in digits after
    # a dot (for example, "sonrie.99"). A numeric final label cannot be a
    # registered DNS top-level domain, so prefer the username interpretation.
    if (
        recognized_type == "INTERNET_NAME"
        and _USERNAME_RE.fullmatch(value)
        and value.rsplit(".", 1)[-1].isdigit()
    ):
        return _quote_username(value) or value

    if recognized_type is None:
        return _quote_username(value) or value
    return value

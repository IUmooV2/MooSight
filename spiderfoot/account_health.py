# -*- coding: utf-8 -*-
"""Reliability scoring for username/account discovery sites.

The Account Finder checks hundreds of third-party endpoints whose behavior can
change independently of MooSight. This module keeps aggregate, username-free
health statistics so a site's historical reliability can inform diagnostics
without treating a transient block or stale fingerprint as a definitive
negative result.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Mapping


_HEALTH_KEYS = ("positive", "negative", "ambiguous", "error")


def empty_health_record() -> dict[str, int | str | None]:
    return {
        "positive": 0,
        "negative": 0,
        "ambiguous": 0,
        "error": 0,
        "last_detail": None,
    }


def normalize_health(data: Mapping | None) -> dict[str, dict[str, int | str | None]]:
    """Normalize persisted site-health data without trusting its schema."""
    if not isinstance(data, Mapping):
        return {}

    normalized = {}
    for raw_name, raw_record in data.items():
        if not isinstance(raw_name, str) or not raw_name.strip() or not isinstance(raw_record, Mapping):
            continue
        record = empty_health_record()
        for key in _HEALTH_KEYS:
            value = raw_record.get(key, 0)
            try:
                value = int(value)
            except (TypeError, ValueError):
                value = 0
            record[key] = max(value, 0)
        detail = raw_record.get("last_detail")
        record["last_detail"] = str(detail)[:240] if detail else None
        normalized[raw_name.strip()] = record
    return normalized


def merge_health(
    historical: Mapping | None,
    current: Mapping | None,
) -> dict[str, dict[str, int | str | None]]:
    """Merge aggregate site-health counters without retaining usernames."""
    merged = normalize_health(historical)
    current_norm = normalize_health(current)

    for name, incoming in current_norm.items():
        record = merged.setdefault(name, empty_health_record())
        for key in _HEALTH_KEYS:
            record[key] = int(record[key]) + int(incoming[key])
        if incoming.get("last_detail"):
            record["last_detail"] = incoming["last_detail"]
    return deepcopy(merged)


def reliability(record: Mapping | None) -> tuple[str, float, int]:
    """Return a conservative reliability label, score, and observation count.

    Positive and clean-negative outcomes are considered resolved observations.
    Ambiguous and error outcomes reduce reliability. Laplace-style smoothing
    avoids overrating a site after only one or two successful checks.
    """
    normalized = normalize_health({"site": record}).get("site", empty_health_record())
    resolved = int(normalized["positive"]) + int(normalized["negative"])
    unresolved = int(normalized["ambiguous"]) + int(normalized["error"])
    total = resolved + unresolved
    score = (resolved + 2) / (total + 4)

    if total < 5:
        label = "NEW"
    elif score >= 0.85:
        label = "HEALTHY"
    elif score >= 0.60:
        label = "MIXED"
    else:
        label = "UNSTABLE"
    return label, score, total


def reliability_text(record: Mapping | None) -> str:
    """Return a compact user-facing site reliability summary."""
    label, score, total = reliability(record)
    if total == 0:
        return "NEW (no history)"
    return f"{label} ({score:.0%}, {total} observation{'s' if total != 1 else ''})"


def dumps_health(data: Mapping | None) -> str:
    """Serialize normalized aggregate health deterministically."""
    return json.dumps(normalize_health(data), sort_keys=True, separators=(",", ":"))


def loads_health(payload: str | bytes | None) -> dict[str, dict[str, int | str | None]]:
    """Parse persisted health defensively, returning an empty model on corruption."""
    if not payload:
        return {}
    if isinstance(payload, bytes):
        try:
            payload = payload.decode("utf-8")
        except UnicodeDecodeError:
            return {}
    if not isinstance(payload, str):
        return {}
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    return normalize_health(data)

# -*- coding: utf-8 -*-
"""Modern CVE/NVD parsing helpers for MooSight.

The helpers are deliberately network-free. They parse NVD CVE API 2.0 payloads
and legacy CIRCL-style payloads into SpiderFoot's existing vulnerability event
shape without broad exception handling.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class VulnerabilityInfo:
    score: float | None
    severity: str | None
    description: str


def severity_from_score(score: float | int | None) -> str | None:
    """Map a CVSS base score to SpiderFoot's severity labels."""
    if score is None:
        return None
    try:
        value = float(score)
    except (TypeError, ValueError):
        return None
    if not 0.0 <= value <= 10.0:
        return None
    if value <= 3.9:
        return "LOW"
    if value <= 6.9:
        return "MEDIUM"
    if value <= 8.9:
        return "HIGH"
    return "CRITICAL"


def _english_description(descriptions: Any) -> str:
    if not isinstance(descriptions, list):
        return "Unknown"
    fallback = None
    for item in descriptions:
        if not isinstance(item, Mapping):
            continue
        value = item.get("value")
        if not isinstance(value, str) or not value.strip():
            continue
        fallback = fallback or value.strip()
        if str(item.get("lang", "")).lower() == "en":
            return value.strip()
    return fallback or "Unknown"


def _metric_info(metrics: Any) -> tuple[float | None, str | None]:
    if not isinstance(metrics, Mapping):
        return None, None

    # Prefer the newest metric generation when multiple scores are present.
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        entries = metrics.get(key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            cvss_data = entry.get("cvssData")
            if not isinstance(cvss_data, Mapping):
                continue
            raw_score = cvss_data.get("baseScore")
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                continue
            severity = cvss_data.get("baseSeverity") or entry.get("baseSeverity")
            if isinstance(severity, str) and severity.strip():
                return score, severity.strip().upper()
            return score, severity_from_score(score)
    return None, None


def parse_nvd_v2(payload: str | bytes | Mapping[str, Any]) -> VulnerabilityInfo | None:
    """Parse one-CVE NVD API 2.0 response payload."""
    if isinstance(payload, bytes):
        try:
            payload = payload.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None
    elif isinstance(payload, Mapping):
        data = payload
    else:
        return None

    vulnerabilities = data.get("vulnerabilities")
    if not isinstance(vulnerabilities, list) or not vulnerabilities:
        return None
    first = vulnerabilities[0]
    if not isinstance(first, Mapping):
        return None
    cve = first.get("cve")
    if not isinstance(cve, Mapping):
        return None

    score, severity = _metric_info(cve.get("metrics"))
    description = _english_description(cve.get("descriptions"))
    return VulnerabilityInfo(score=score, severity=severity, description=description)


def parse_circl(payload: str | bytes | Mapping[str, Any]) -> VulnerabilityInfo | None:
    """Parse the legacy CIRCL response shape used by SpiderFoot."""
    if isinstance(payload, bytes):
        try:
            payload = payload.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None
    elif isinstance(payload, Mapping):
        data = payload
    else:
        return None

    raw_score = data.get("cvss")
    try:
        score = float(raw_score) if raw_score is not None else None
    except (TypeError, ValueError):
        score = None
    description = data.get("summary")
    if not isinstance(description, str) or not description.strip():
        description = "Unknown"
    return VulnerabilityInfo(
        score=score,
        severity=severity_from_score(score),
        description=description.strip(),
    )


def event_type(info: VulnerabilityInfo | None) -> str:
    """Return the existing SpiderFoot vulnerability event type."""
    if info is None or not info.severity:
        return "VULNERABILITY_GENERAL"
    severity = info.severity.upper()
    if severity not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        severity = severity_from_score(info.score) or ""
    return f"VULNERABILITY_CVE_{severity}" if severity else "VULNERABILITY_GENERAL"


def format_cve_result(cve_id: str, info: VulnerabilityInfo | None) -> tuple[str, str]:
    """Format CVE details using SpiderFoot's established tuple contract."""
    event = event_type(info)
    score = "Unknown" if info is None or info.score is None else f"{info.score:g}"
    description = "Unknown" if info is None else info.description
    return (
        event,
        f"{cve_id}\n<SFURL>https://nvd.nist.gov/vuln/detail/{cve_id}</SFURL>\n"
        f"Score: {score}\nDescription: {description}",
    )

# -*- coding: utf-8 -*-
"""Compatibility helpers between MooSight networking and legacy SpiderFoot APIs.

The existing module ecosystem expects ``SpiderFoot.fetchUrl`` to return a
plain dictionary. New networking code uses ``NetworkResult``. Keeping the
translation in one small module lets the transport layer modernize without
forcing hundreds of modules to change at once.
"""

from __future__ import annotations

from typing import Any

from spiderfoot.network import NetworkResult, NetworkState


LEGACY_EMPTY_RESULT = {
    "code": None,
    "status": None,
    "content": None,
    "headers": None,
    "realurl": None,
}


def network_result_to_legacy(result: NetworkResult, *, decode_content: bool = True) -> dict[str, Any]:
    """Convert a ``NetworkResult`` to the historical ``fetchUrl`` dictionary.

    Compatibility rules:
    - HTTP status remains a string because legacy modules compare against values
      such as ``"200"``.
    - ``realurl`` is always populated from the normalized/redacted result URL.
    - routine network failure is exposed in ``status`` without pretending it
      was a definitive 404/not-found result.
    - byte content is decoded with UTF-8, then ASCII, and finally kept as bytes,
      matching the broad behavior of the historical implementation.
    """
    if not isinstance(result, NetworkResult):
        raise TypeError("result must be a NetworkResult")

    content = result.content
    if decode_content and isinstance(content, bytes):
        for encoding in ("utf-8", "ascii"):
            try:
                content = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

    status = None
    if result.state not in {NetworkState.SUCCESS, NetworkState.NOT_FOUND}:
        status = result.error or result.state.value

    return {
        "code": str(result.status_code) if result.status_code is not None else None,
        "status": status,
        "content": content,
        "headers": dict(result.headers) if result.headers else {},
        "realurl": result.url,
    }


def to_legacy_result(
    result: NetworkResult,
    *,
    requested_url: str | None = None,
    disable_content_encoding: bool = False,
) -> dict[str, Any]:
    """Compatibility wrapper used by the modern fetch/client layers.

    Earlier migration code adopted the ``to_legacy_result`` name and passes the
    originally requested URL plus SpiderFoot's historical
    ``disableContentEncoding`` setting. Keep that stable seam while delegating
    the actual conversion to ``network_result_to_legacy``.
    """
    legacy = network_result_to_legacy(
        result,
        decode_content=not disable_content_encoding,
    )
    if legacy["realurl"] is None:
        legacy["realurl"] = requested_url
    return legacy


def empty_legacy_result(url: str | None = None) -> dict[str, Any]:
    """Return a fresh legacy result dictionary without sharing mutable state."""
    result = dict(LEGACY_EMPTY_RESULT)
    result["realurl"] = url
    return result

# -*- coding: utf-8 -*-
"""Scoped TLS helpers for MooSight.

The legacy SpiderFoot core modifies Python's process-wide HTTPS behavior and
uses deprecated ``ssl.wrap_socket`` APIs. This module provides explicit,
instance-independent helpers for verified TLS by default and narrowly scoped
unverified handshakes when a module's purpose genuinely requires observing a
broken certificate.
"""

from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass


@dataclass(frozen=True)
class TLSSettings:
    """Settings for one TLS connection."""

    verify: bool = True
    timeout: float = 10.0
    server_hostname: str | None = None

    def __post_init__(self) -> None:
        if self.timeout <= 0:
            raise ValueError("timeout must be greater than zero")


def create_tls_context(*, verify: bool = True) -> ssl.SSLContext:
    """Return a TLS client context without modifying process-wide defaults."""
    if verify:
        return ssl.create_default_context()

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def open_tcp_socket(host: str, port: int, timeout: float = 10.0) -> socket.socket:
    """Open a bounded TCP connection using modern socket helpers."""
    if not isinstance(host, str) or not host.strip():
        raise ValueError("host must be a non-empty string")
    try:
        port = int(port)
    except (TypeError, ValueError) as exc:
        raise ValueError("port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")

    return socket.create_connection((host.strip(), port), timeout=timeout)


def open_tls_socket(
    host: str,
    port: int,
    *,
    settings: TLSSettings | None = None,
    context: ssl.SSLContext | None = None,
) -> ssl.SSLSocket:
    """Open one TLS socket with explicit verification semantics.

    A custom ``SSLContext`` may be supplied for certificate-analysis modules.
    The caller owns the returned socket and should close it using a context
    manager or ``close()``.
    """
    settings = settings or TLSSettings(server_hostname=host)
    if not isinstance(settings, TLSSettings):
        raise TypeError("settings must be TLSSettings")

    server_hostname = settings.server_hostname or host
    tls_context = context or create_tls_context(verify=settings.verify)

    raw_socket = open_tcp_socket(host, port, timeout=settings.timeout)
    try:
        return tls_context.wrap_socket(raw_socket, server_hostname=server_hostname)
    except Exception:
        raw_socket.close()
        raise


def create_tls_socket(
    host: str,
    port: int,
    timeout: float = 10.0,
    *,
    verify: bool = True,
    server_hostname: str | None = None,
) -> ssl.SSLSocket:
    """Compatibility facade used by the modern SpiderFoot network mixin.

    Keep the historical positional ``host, port, timeout`` calling convention
    while delegating all TLS behavior to :func:`open_tls_socket`.
    """
    settings = TLSSettings(
        verify=verify,
        timeout=float(timeout),
        server_hostname=server_hostname or host,
    )
    return open_tls_socket(host, port, settings=settings)

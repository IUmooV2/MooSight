# -*- coding: utf-8 -*-
"""Certificate parsing helpers for MooSight.

This module keeps certificate inspection side-effect free and avoids the legacy
``BaseException`` handlers in ``sflib.py``. Parsing failures are represented in
the returned compatibility dictionary while process-control exceptions continue
to propagate normally.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import cryptography
import OpenSSL
from cryptography import x509
from cryptography.x509.oid import NameOID


def _certificate_expiry(raw_not_after: bytes) -> tuple[int, str]:
    value = raw_not_after.decode("ascii")
    parsed = datetime.strptime(value, "%Y%m%d%H%M%SZ").replace(tzinfo=timezone.utc)
    return int(parsed.timestamp()), parsed.strftime("%Y-%m-%d %H:%M:%S")


def parse_certificate(rawcert: str | bytes, fqdn: str | None = None, expiringdays: int = 30) -> dict | None:
    """Parse a PEM certificate into SpiderFoot's historical result shape."""
    if not rawcert:
        return None
    if not isinstance(expiringdays, int) or expiringdays < 0:
        raise ValueError("expiringdays must be a non-negative integer")

    if isinstance(rawcert, str):
        raw_bytes = rawcert.replace("\r", "").encode("utf-8")
    elif isinstance(rawcert, bytes):
        raw_bytes = rawcert.replace(b"\r", b"")
    else:
        raise TypeError("rawcert must be str or bytes")

    cert = x509.load_pem_x509_certificate(raw_bytes)
    sslcert = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, raw_bytes)
    sslcert_dump = OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_TEXT, sslcert)

    result = {
        "text": sslcert_dump.decode("utf-8", errors="replace"),
        "issuer": str(cert.issuer),
        "altnames": [],
        "expired": False,
        "expiring": False,
        "mismatch": False,
        "certerror": False,
        "issued": str(cert.subject),
    }

    try:
        expiry, expiry_text = _certificate_expiry(sslcert.get_notAfter())
        result["expiry"] = expiry
        result["expirystr"] = expiry_text
        now = int(time.time())
        result["expiring"] = expiry <= now + expiringdays * 86400
        result["expired"] = expiry <= now
    except (AttributeError, UnicodeDecodeError, ValueError, TypeError):
        result["certerror"] = True
        return result

    try:
        extension = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        result["altnames"] = [
            name.value.lower().encode("raw_unicode_escape").decode("ascii", errors="replace")
            for name in extension.value
            if isinstance(name, x509.DNSName)
        ]
    except x509.ExtensionNotFound:
        pass

    certificate_hosts: list[str] = []
    try:
        attributes = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if len(attributes) == 1:
            common_name = attributes[0].value.lower()
            if common_name not in result["altnames"]:
                certificate_hosts.append(common_name)
    except (AttributeError, TypeError, ValueError):
        result["certerror"] = True

    if fqdn and result["issued"]:
        if not isinstance(fqdn, str):
            raise TypeError("fqdn must be a string or None")
        fqdn = fqdn.lower()
        if f"cn={fqdn}" in result["issued"].lower():
            certificate_hosts.append(fqdn)
        certificate_hosts.extend(host.replace("dns:", "") for host in result["altnames"])
        result["hosts"] = certificate_hosts

        fqdn_tld = ".".join(fqdn.split(".")[1:]).lower()
        result["mismatch"] = not any(
            host == fqdn or host == f"*.{fqdn_tld}" or host == fqdn_tld
            for host in certificate_hosts
        )

    return result

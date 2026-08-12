# -*- coding: utf-8 -*-
"""Modernized SpiderFoot core facade used during MooSight migration.

This class intentionally leaves the legacy ``sflib.SpiderFoot`` implementation
available while giving MooSight a drop-in core whose networking methods are
resolved from ``ModernNetworkMixin`` first. That lets us exercise the modern
transport stack before deleting the large legacy networking block from sflib.
"""

from __future__ import annotations

import logging
import socket
import urllib.parse
from copy import deepcopy

import netaddr

from sflib import SpiderFoot as LegacySpiderFoot
from spiderfoot.certificates import parse_certificate
from spiderfoot.modern_network_mixin import ModernNetworkMixin
from spiderfoot.security import redact_url
from spiderfoot.vulnerabilities import format_cve_result, parse_circl, parse_nvd_v2


class ModernSpiderFoot(ModernNetworkMixin, LegacySpiderFoot):
    """Legacy SpiderFoot behavior with MooSight's modern networking overrides.

    Method resolution order is deliberate: networking methods implemented by
    ``ModernNetworkMixin`` win over the historical implementations in
    ``LegacySpiderFoot``. All unrelated legacy behavior remains available.

    The modern constructor does not invoke ``LegacySpiderFoot.__init__`` because
    the legacy constructor mutates process-wide TLS and DNS/socket behavior.
    Only the safe instance initialization needed by the rest of SpiderFoot is
    reproduced here.
    """

    def __init__(self, options: dict) -> None:
        if not isinstance(options, dict):
            raise TypeError(f"options is {type(options)}; expected dict()")

        self.opts = deepcopy(options)
        self.log = logging.getLogger("spiderfoot.sflib")
        self._modern_http_client = None
        self._modern_fetch_service = None

    def optValueToData(self, val: str) -> str | None:
        """Resolve an option value without bypassing the modern network stack.

        ``@path`` values are read as UTF-8 text and HTTP(S) values are fetched
        through :meth:`fetchUrl`, preserving configured proxy, timeout, TLS,
        retry, and redaction behavior. Plain strings are returned unchanged.
        """
        if not isinstance(val, str):
            self.error(f"Invalid option value {val}")
            return None

        if val.startswith("@"):
            path = val[1:]
            if not path:
                self.error("Invalid empty option file path")
                return None
            self.info(f"Loading configuration data from: {path}")
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    return handle.read()
            except (OSError, UnicodeError) as exc:
                self.error(f"Unable to open option file, {path}: {exc}")
                return None

        if val.lower().startswith(("http://", "https://")):
            self.info(f"Downloading configuration data from: {redact_url(val)}")
            result = self.fetchUrl(
                val,
                timeout=int(self.opts.get("_fetchtimeout", 5)),
                useragent=self.opts.get("_useragent", "SpiderFoot"),
                noLog=True,
                verify=True,
            )
            if not result or not result.get("content"):
                self.error(f"Unable to open option URL, {redact_url(val)}")
                return None

            content = result["content"]
            if isinstance(content, bytes):
                try:
                    return content.decode("utf-8")
                except UnicodeDecodeError as exc:
                    self.error(f"Unable to decode option URL, {redact_url(val)}: {exc}")
                    return None
            return str(content)

        return val

    def validIpNetwork(self, cidr: str) -> bool:
        """Validate CIDR input without catching process-control exceptions."""
        if not isinstance(cidr, str) or "/" not in cidr:
            return False
        try:
            return netaddr.IPNetwork(cidr).size > 0
        except (netaddr.AddrFormatError, ValueError, TypeError):
            return False

    def resolveHost(self, host: str) -> list:
        """Resolve IPv4 addresses while preserving interrupts and exits."""
        if not host:
            self.error(f"Unable to resolve host: {host} (Invalid host)")
            return []
        try:
            addrs = self.normalizeDNS(socket.gethostbyname_ex(host))
        except (OSError, UnicodeError, ValueError) as exc:
            self.debug(f"Unable to resolve host: {host} ({exc})")
            return []
        return list(set(addrs)) if addrs else []

    def resolveIP(self, ipaddr: str) -> list:
        """Reverse-resolve an IP without swallowing process-control exceptions."""
        if not self.validIP(ipaddr) and not self.validIP6(ipaddr):
            self.error(f"Unable to reverse resolve {ipaddr} (Invalid IP address)")
            return []
        try:
            addrs = self.normalizeDNS(socket.gethostbyaddr(ipaddr))
        except (OSError, UnicodeError, ValueError) as exc:
            self.debug(f"Unable to reverse resolve IP address: {ipaddr} ({exc})")
            return []
        return list(set(addrs)) if addrs else []

    def resolveHost6(self, hostname: str) -> list:
        """Resolve IPv6 addresses without broad BaseException handling."""
        if not hostname:
            self.error(f"Unable to resolve host: {hostname} (Invalid host)")
            return []

        addrs: list[str] = []
        try:
            for addr in socket.getaddrinfo(hostname, None, socket.AF_INET6):
                resolved = addr[4][0]
                if resolved not in addrs:
                    addrs.append(resolved)
        except (OSError, UnicodeError, ValueError) as exc:
            self.debug(f"Unable to resolve host: {hostname} ({exc})")
            return []
        return addrs

    def parseCert(self, rawcert: str | bytes, fqdn: str = None, expiringdays: int = 30) -> dict | None:
        """Parse certificates without using legacy ``BaseException`` handlers."""
        if not rawcert:
            self.error(f"Invalid certificate: {rawcert}")
            return None
        try:
            return parse_certificate(rawcert, fqdn=fqdn, expiringdays=expiringdays)
        except (ValueError, TypeError) as exc:
            self.error(f"Error processing certificate: {exc}")
            return {
                "text": "",
                "issuer": "",
                "altnames": [],
                "expired": False,
                "expiring": False,
                "mismatch": False,
                "certerror": True,
                "issued": "",
            }

    def cveInfo(self, cveId: str, sources: str = "nist,circl") -> tuple[str, str]:
        """Look up a CVE using the modern NVD 2.0 response format first.

        The public return contract remains SpiderFoot's ``(event_type, text)``
        tuple. Network access goes through the modern fetch stack, cache entries
        are source/schema-specific, and malformed payloads are treated as an
        unknown result without broad ``BaseException`` handling.
        """
        if not isinstance(cveId, str) or not cveId.strip():
            return format_cve_result(str(cveId or "Unknown"), None)

        cve_id = cveId.strip().upper()
        requested_sources = [source.strip().lower() for source in str(sources).split(",") if source.strip()]
        if not requested_sources:
            requested_sources = ["nist", "circl"]

        for source in requested_sources:
            if source not in {"nist", "circl"}:
                continue

            cache_key = f"{source}-modern-{cve_id}"
            payload = self.cacheGet(cache_key, 24)

            if not payload:
                if source == "nist":
                    query = urllib.parse.urlencode({"cveIds": cve_id})
                    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?{query}"
                else:
                    url = f"https://cve.circl.lu/api/cve/{urllib.parse.quote(cve_id, safe='')}"

                response = self.fetchUrl(url, timeout=10, noLog=True)
                if not response or response.get("code") != "200" or not response.get("content"):
                    continue
                payload = response["content"]
                try:
                    self.cachePut(cache_key, payload)
                except (OSError, UnicodeError, TypeError, ValueError) as exc:
                    self.debug(f"Unable to cache CVE response from {source.upper()}: {exc}")

            if source == "nist":
                info = parse_nvd_v2(payload)
            else:
                info = parse_circl(payload)

            if info is not None:
                return format_cve_result(cve_id, info)

            self.debug(f"Unable to parse CVE response from {source.upper()}")

        return format_cve_result(cve_id, None)

    def close(self) -> None:
        """Release resources owned by the modern core facade."""
        self.closeNetworkClient()

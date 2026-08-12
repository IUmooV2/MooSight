#!/usr/bin/env python3
"""Shared manifest for MooSight-owned modern runtime and verification code.

Keeping this list in one place prevents security and quality gates from silently
covering different files as modernization continues.
"""

from __future__ import annotations


MODERN_PYTHON_FILES = (
    "moosight.py",
    "spiderfoot/config.py",
    "spiderfoot/http_client.py",
    "spiderfoot/legacy_fetch.py",
    "spiderfoot/logger.py",
    "spiderfoot/modern_core.py",
    "spiderfoot/modern_network_mixin.py",
    "spiderfoot/modern_scanner.py",
    "spiderfoot/network.py",
    "spiderfoot/network_legacy.py",
    "spiderfoot/security.py",
    "spiderfoot/tls.py",
    "tools/audit_mutable_class_state.py",
    "tools/audit_security.py",
    "tools/exception_audit.py",
    "tools/modern_files.py",
    "tools/preflight.py",
    "tools/verify_exception_policy.py",
    "tools/verify_modern_runtime.py",
    "tools/verify_modern_security.py",
)

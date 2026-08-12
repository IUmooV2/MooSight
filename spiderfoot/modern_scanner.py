# -*- coding: utf-8 -*-
"""Modern scanner facade for MooSight.

This transitional subclass keeps the legacy scanner orchestration while making
scan-owned mutable collections instance-local. It also ensures the module list
passed by a caller cannot be mutated through scanner internals.
"""

from __future__ import annotations

from sfscan import SpiderFootScanner as LegacySpiderFootScanner


class ModernSpiderFootScanner(LegacySpiderFootScanner):
    """Legacy scanner behavior with isolated per-scan mutable state."""

    def __init__(
        self,
        scanName: str,
        scanId: str,
        targetValue: str,
        targetType: str,
        moduleList: list,
        globalOpts: dict,
        start: bool = True,
    ) -> None:
        # These attributes are historically defined as mutable class values in
        # SpiderFootScanner. Assigning them here guarantees each scanner owns
        # independent collections even before legacy initialization touches them.
        self._SpiderFootScanner__moduleList = []
        self._SpiderFootScanner__moduleInstances = {}
        self._SpiderFootScanner__modconfig = {}

        # Pass an owned copy because the legacy initializer stores the list by
        # reference. This prevents scan setup from ever mutating caller state.
        owned_modules = list(moduleList) if isinstance(moduleList, list) else moduleList

        super().__init__(
            scanName,
            scanId,
            targetValue,
            targetType,
            owned_modules,
            globalOpts,
            start=start,
        )

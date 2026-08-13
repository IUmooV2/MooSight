# -*- coding: utf-8 -*-
"""Modern web-UI facade for MooSight."""

from __future__ import annotations

import cherrypy

from sfwebui import SpiderFootWebUi as LegacySpiderFootWebUi
from spiderfoot import SpiderFootHelpers
from spiderfoot.target_input import normalize_scan_target


class ModernSpiderFootWebUi(LegacySpiderFootWebUi):
    """Legacy web UI with friendlier scan-target input handling."""

    @cherrypy.expose
    def startscan(self, scanname: str, scantarget: str, modulelist: str, typelist: str, usecase: str) -> str:
        recognized = SpiderFootHelpers.targetTypeFromString(scantarget) if isinstance(scantarget, str) else None
        normalized = normalize_scan_target(scantarget, recognized_type=recognized)
        return super().startscan(scanname, normalized, modulelist, typelist, usecase)

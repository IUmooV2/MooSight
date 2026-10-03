#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MooSight application entry point.

This transitional entry point keeps SpiderFoot's existing CLI/web startup code
intact while routing runtime core, scanner, and web-UI construction through
MooSight's modern compatibility facades.
"""

from __future__ import annotations

import warnings

_WARNING_FILTERS_BEFORE_LEGACY_IMPORTS = list(warnings.filters)
try:
    import sf
    import sfscan
    import sfwebui
    from spiderfoot.modern_core import ModernSpiderFoot
    from spiderfoot.modern_scanner import ModernSpiderFootScanner
    from spiderfoot.modern_webui import ModernSpiderFootWebUi
finally:
    warnings.filters[:] = _WARNING_FILTERS_BEFORE_LEGACY_IMPORTS
    del _WARNING_FILTERS_BEFORE_LEGACY_IMPORTS


def install_modern_core() -> None:
    """Install MooSight's modern runtime facades into legacy startup modules."""
    sf.SpiderFoot = ModernSpiderFoot
    sfscan.SpiderFoot = ModernSpiderFoot
    sfscan.SpiderFootScanner = ModernSpiderFootScanner

    # sf.py imported the web-UI class and sfwebui.py imported SpiderFoot by value,
    # so both bindings must be replaced explicitly.
    sf.SpiderFootWebUi = ModernSpiderFootWebUi
    sfwebui.SpiderFoot = ModernSpiderFoot


def main() -> None:
    install_modern_core()
    sf.main()


if __name__ == "__main__":
    main()

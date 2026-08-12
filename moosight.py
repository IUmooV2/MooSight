#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MooSight application entry point.

This transitional entry point keeps SpiderFoot's existing CLI/web startup code
intact while routing runtime core and scanner construction through MooSight's
modern compatibility facades.
"""

from __future__ import annotations

import sf
import sfscan
from spiderfoot.modern_core import ModernSpiderFoot
from spiderfoot.modern_scanner import ModernSpiderFootScanner


def install_modern_core() -> None:
    """Install MooSight's modern core and scanner into legacy startup modules."""
    sf.SpiderFoot = ModernSpiderFoot
    sfscan.SpiderFoot = ModernSpiderFoot
    sfscan.SpiderFootScanner = ModernSpiderFootScanner


def main() -> None:
    install_modern_core()
    sf.main()


if __name__ == "__main__":
    main()

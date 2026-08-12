#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MooSight application entry point.

This transitional entry point keeps SpiderFoot's existing CLI/web startup code
intact while routing runtime core construction through ``ModernSpiderFoot``.
It avoids a risky in-place rewrite of ``sf.py`` and ``sfscan.py`` during the
modernization phase.
"""

from __future__ import annotations

import sf
import sfscan
from spiderfoot.modern_core import ModernSpiderFoot


def install_modern_core() -> None:
    """Install the modern core into the legacy startup modules.

    ``sf.py`` and ``sfscan.py`` resolve their imported ``SpiderFoot`` symbol at
    runtime when creating core instances. Rebinding those module globals keeps
    all existing startup/CLI behavior while making new instances use MooSight's
    modern networking implementation.
    """
    sf.SpiderFoot = ModernSpiderFoot
    sfscan.SpiderFoot = ModernSpiderFoot


def main() -> None:
    install_modern_core()
    sf.main()


if __name__ == "__main__":
    main()

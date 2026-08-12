import unittest
from unittest.mock import patch

import moosight
import sf
import sfscan
from spiderfoot.modern_core import ModernSpiderFoot


class TestMooSightEntrypoint(unittest.TestCase):

    def setUp(self):
        self.original_sf_core = sf.SpiderFoot
        self.original_scan_core = sfscan.SpiderFoot

    def tearDown(self):
        sf.SpiderFoot = self.original_sf_core
        sfscan.SpiderFoot = self.original_scan_core

    def test_install_modern_core_routes_cli_and_scanner(self):
        moosight.install_modern_core()
        self.assertIs(sf.SpiderFoot, ModernSpiderFoot)
        self.assertIs(sfscan.SpiderFoot, ModernSpiderFoot)

    def test_install_modern_core_is_idempotent(self):
        moosight.install_modern_core()
        moosight.install_modern_core()
        self.assertIs(sf.SpiderFoot, ModernSpiderFoot)
        self.assertIs(sfscan.SpiderFoot, ModernSpiderFoot)

    def test_main_installs_modern_core_before_delegating(self):
        with patch.object(sf, "main") as legacy_main:
            moosight.main()

        self.assertIs(sf.SpiderFoot, ModernSpiderFoot)
        self.assertIs(sfscan.SpiderFoot, ModernSpiderFoot)
        legacy_main.assert_called_once_with()

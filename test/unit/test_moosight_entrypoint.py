import unittest
from unittest.mock import patch

import moosight
import sf
import sfscan
import sfwebui
from spiderfoot.modern_core import ModernSpiderFoot
from spiderfoot.modern_scanner import ModernSpiderFootScanner
from spiderfoot.modern_webui import ModernSpiderFootWebUi


class TestMooSightEntrypoint(unittest.TestCase):

    def setUp(self):
        self.original_sf_core = sf.SpiderFoot
        self.original_scan_core = sfscan.SpiderFoot
        self.original_scanner = sfscan.SpiderFootScanner
        self.original_webui = sf.SpiderFootWebUi
        self.original_webui_core = sfwebui.SpiderFoot

    def tearDown(self):
        sf.SpiderFoot = self.original_sf_core
        sfscan.SpiderFoot = self.original_scan_core
        sfscan.SpiderFootScanner = self.original_scanner
        sf.SpiderFootWebUi = self.original_webui
        sfwebui.SpiderFoot = self.original_webui_core

    def test_install_modern_core_routes_cli_scanner_and_webui(self):
        moosight.install_modern_core()
        self.assertIs(sf.SpiderFoot, ModernSpiderFoot)
        self.assertIs(sfscan.SpiderFoot, ModernSpiderFoot)
        self.assertIs(sfscan.SpiderFootScanner, ModernSpiderFootScanner)
        self.assertIs(sf.SpiderFootWebUi, ModernSpiderFootWebUi)
        self.assertIs(sfwebui.SpiderFoot, ModernSpiderFoot)

    def test_install_modern_core_is_idempotent(self):
        moosight.install_modern_core()
        moosight.install_modern_core()
        self.assertIs(sf.SpiderFoot, ModernSpiderFoot)
        self.assertIs(sfscan.SpiderFoot, ModernSpiderFoot)
        self.assertIs(sf.SpiderFootWebUi, ModernSpiderFootWebUi)

    def test_main_installs_modern_core_before_delegating(self):
        with patch.object(sf, "main") as legacy_main:
            moosight.main()

        self.assertIs(sf.SpiderFoot, ModernSpiderFoot)
        self.assertIs(sfscan.SpiderFoot, ModernSpiderFoot)
        self.assertIs(sfscan.SpiderFootScanner, ModernSpiderFootScanner)
        self.assertIs(sf.SpiderFootWebUi, ModernSpiderFootWebUi)
        self.assertIs(sfwebui.SpiderFoot, ModernSpiderFoot)
        legacy_main.assert_called_once_with()

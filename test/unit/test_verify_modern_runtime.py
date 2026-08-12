import ssl
import unittest

import sf
import sfscan

from spiderfoot.modern_core import ModernSpiderFoot
from tools.verify_modern_runtime import verify_runtime


class TestModernRuntimeVerifier(unittest.TestCase):

    def test_verify_runtime_passes_without_network_access(self):
        before = ssl._create_default_https_context
        checks = verify_runtime()

        self.assertTrue(checks)
        self.assertTrue(all(check.ok for check in checks), [check.detail for check in checks])
        self.assertIs(ssl._create_default_https_context, before)
        self.assertIs(sf.SpiderFoot, ModernSpiderFoot)
        self.assertIs(sfscan.SpiderFoot, ModernSpiderFoot)

    def test_check_names_are_unique(self):
        checks = verify_runtime()
        names = [check.name for check in checks]
        self.assertEqual(len(names), len(set(names)))

import socket
import ssl
import unittest

import sf
import sfscan
import sfwebui

from spiderfoot.modern_core import ModernSpiderFoot
from spiderfoot.modern_scanner import ModernSpiderFootScanner
from spiderfoot.modern_webui import ModernSpiderFootWebUi
from tools.verify_modern_runtime import verify_runtime


class TestModernRuntimeVerifier(unittest.TestCase):

    def test_verify_runtime_passes_without_network_access(self):
        before_tls = ssl._create_default_https_context
        resolver_names = (
            "getaddrinfo",
            "getnameinfo",
            "getfqdn",
            "gethostbyname",
            "gethostbyname_ex",
            "gethostbyaddr",
        )
        before_resolver = {
            name: getattr(socket, name)
            for name in resolver_names
            if hasattr(socket, name)
        }

        checks = verify_runtime()

        self.assertTrue(checks)
        self.assertTrue(all(check.ok for check in checks), [check.detail for check in checks])
        self.assertIs(ssl._create_default_https_context, before_tls)
        for name, function in before_resolver.items():
            with self.subTest(name=name):
                self.assertIs(getattr(socket, name), function)
        self.assertIs(sf.SpiderFoot, ModernSpiderFoot)
        self.assertIs(sfscan.SpiderFoot, ModernSpiderFoot)
        self.assertIs(sfscan.SpiderFootScanner, ModernSpiderFootScanner)
        self.assertIs(sf.SpiderFootWebUi, ModernSpiderFootWebUi)
        self.assertIs(sfwebui.SpiderFoot, ModernSpiderFoot)

    def test_runtime_verifier_includes_global_resolver_check(self):
        checks = verify_runtime()
        by_name = {check.name: check for check in checks}
        self.assertIn("global DNS resolver preservation", by_name)
        self.assertTrue(by_name["global DNS resolver preservation"].ok)

    def test_runtime_verifier_includes_scanner_facade_check(self):
        checks = verify_runtime()
        by_name = {check.name: check for check in checks}
        self.assertIn("scanner facade routing", by_name)
        self.assertTrue(by_name["scanner facade routing"].ok)

    def test_runtime_verifier_includes_web_ui_checks(self):
        checks = verify_runtime()
        by_name = {check.name: check for check in checks}
        self.assertTrue(by_name["web UI facade routing"].ok)
        self.assertTrue(by_name["web UI core routing"].ok)
        self.assertTrue(by_name["web startscan exposure"].ok)

    def test_check_names_are_unique(self):
        checks = verify_runtime()
        names = [check.name for check in checks]
        self.assertEqual(len(names), len(set(names)))

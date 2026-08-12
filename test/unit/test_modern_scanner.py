import unittest
from unittest.mock import patch

from sfscan import SpiderFootScanner as LegacySpiderFootScanner
from spiderfoot.modern_scanner import ModernSpiderFootScanner


class TestModernSpiderFootScanner(unittest.TestCase):

    @patch.object(LegacySpiderFootScanner, "__init__", return_value=None)
    def test_passes_owned_module_list_to_legacy_initializer(self, legacy_init):
        modules = ["sfp_example"]
        scanner = ModernSpiderFootScanner(
            "scan",
            "scan-id",
            "example.com",
            "INTERNET_NAME",
            modules,
            {"x": 1},
            start=False,
        )

        args = legacy_init.call_args.args
        passed_modules = args[4]
        self.assertEqual(passed_modules, modules)
        self.assertIsNot(passed_modules, modules)
        self.assertEqual(scanner._SpiderFootScanner__moduleInstances, {})
        self.assertEqual(scanner._SpiderFootScanner__modconfig, {})

    @patch.object(LegacySpiderFootScanner, "__init__", return_value=None)
    def test_scanner_instances_do_not_share_mutable_state(self, _legacy_init):
        first = ModernSpiderFootScanner(
            "scan-one", "1", "one.example", "INTERNET_NAME", ["a"], {"x": 1}, start=False
        )
        second = ModernSpiderFootScanner(
            "scan-two", "2", "two.example", "INTERNET_NAME", ["b"], {"x": 1}, start=False
        )

        first._SpiderFootScanner__moduleInstances["a"] = object()
        first._SpiderFootScanner__modconfig["a"] = {"enabled": True}

        self.assertEqual(second._SpiderFootScanner__moduleInstances, {})
        self.assertEqual(second._SpiderFootScanner__modconfig, {})
        self.assertIsNot(
            first._SpiderFootScanner__moduleInstances,
            second._SpiderFootScanner__moduleInstances,
        )
        self.assertIsNot(first._SpiderFootScanner__modconfig, second._SpiderFootScanner__modconfig)

    @patch.object(LegacySpiderFootScanner, "__init__", return_value=None)
    def test_non_list_module_input_is_left_for_legacy_validation(self, legacy_init):
        ModernSpiderFootScanner(
            "scan", "id", "example.com", "INTERNET_NAME", None, {"x": 1}, start=False
        )
        self.assertIsNone(legacy_init.call_args.args[4])

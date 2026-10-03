import unittest
from unittest.mock import patch

from spiderfoot.certificates import _certificate_expiry, parse_certificate
from spiderfoot.modern_core import ModernSpiderFoot


class TestCertificateHelpers(unittest.TestCase):

    def test_certificate_expiry_is_utc_and_portable(self):
        timestamp, text = _certificate_expiry(b"20300102030405Z")
        self.assertEqual(text, "2030-01-02 03:04:05")
        self.assertGreater(timestamp, 0)

    def test_parse_certificate_rejects_invalid_types(self):
        with self.assertRaises(TypeError):
            parse_certificate(123)

    def test_parse_certificate_rejects_negative_expiring_days(self):
        with self.assertRaises(ValueError):
            parse_certificate("certificate", expiringdays=-1)

    def _core(self):
        return ModernSpiderFoot({
            "_debug": False,
            "__logging": False,
            "_fetchtimeout": 5,
            "_useragent": "MooSight-Test",
        })

    @patch("spiderfoot.modern_core.parse_certificate")
    def test_modern_core_routes_certificate_parsing_to_helper(self, parser):
        parser.return_value = {"certerror": False, "issuer": "example"}
        core = self._core()
        try:
            result = core.parseCert("PEM", fqdn="example.com", expiringdays=14)
            self.assertEqual(result["issuer"], "example")
            parser.assert_called_once_with("PEM", fqdn="example.com", expiringdays=14)
        finally:
            core.close()

    @patch("spiderfoot.modern_core.parse_certificate", side_effect=KeyboardInterrupt)
    def test_modern_core_does_not_swallow_keyboard_interrupt(self, _parser):
        core = self._core()
        try:
            with self.assertRaises(KeyboardInterrupt):
                core.parseCert("PEM")
        finally:
            core.close()

    @patch("spiderfoot.modern_core.parse_certificate", side_effect=ValueError("bad cert"))
    def test_expected_parse_error_returns_compatibility_result(self, _parser):
        core = self._core()
        try:
            result = core.parseCert("PEM")
            self.assertTrue(result["certerror"])
            self.assertEqual(result["altnames"], [])
        finally:
            core.close()


if __name__ == "__main__":
    unittest.main()

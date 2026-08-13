import json
import unittest
from unittest.mock import patch

from spiderfoot.modern_core import ModernSpiderFoot


class TestModernCveInfo(unittest.TestCase):

    def _options(self):
        return {
            "_debug": False,
            "__logging": False,
            "_fetchtimeout": 5,
            "_useragent": "MooSight-Test",
            "_dnsserver": "",
            "_socks1type": "",
            "_socks2addr": "",
            "_socks3port": "",
            "_socks4user": "",
            "_socks5pwd": "",
        }

    def _nvd_payload(self):
        return json.dumps({
            "vulnerabilities": [{
                "cve": {
                    "descriptions": [{"lang": "en", "value": "Modern NVD response"}],
                    "metrics": {
                        "cvssMetricV31": [{
                            "cvssData": {"baseScore": 8.8, "baseSeverity": "HIGH"}
                        }]
                    },
                }
            }]
        })

    @patch.object(ModernSpiderFoot, "cachePut")
    @patch.object(ModernSpiderFoot, "cacheGet", return_value=None)
    @patch.object(ModernSpiderFoot, "fetchUrl")
    def test_nist_lookup_uses_nvd_v2_and_modern_fetch(self, fetch, cache_get, cache_put):
        fetch.return_value = {
            "code": "200",
            "content": self._nvd_payload(),
            "headers": {},
            "realurl": "https://services.nvd.nist.gov/",
            "status": None,
        }
        core = ModernSpiderFoot(self._options())
        try:
            event, text = core.cveInfo("cve-2026-1234", sources="nist")
        finally:
            core.close()

        self.assertEqual(event, "VULNERABILITY_CVE_HIGH")
        self.assertIn("Score: 8.8", text)
        self.assertIn("Modern NVD response", text)
        url = fetch.call_args.args[0]
        self.assertIn("/rest/json/cves/2.0?", url)
        self.assertIn("cveIds=CVE-2026-1234", url)
        self.assertEqual(fetch.call_args.kwargs["timeout"], 10)
        self.assertTrue(fetch.call_args.kwargs["noLog"])
        cache_get.assert_called_once_with("nist-modern-CVE-2026-1234", 24)
        cache_put.assert_called_once()

    @patch.object(ModernSpiderFoot, "fetchUrl")
    @patch.object(ModernSpiderFoot, "cacheGet")
    def test_cached_nvd_payload_avoids_network(self, cache_get, fetch):
        cache_get.return_value = self._nvd_payload()
        core = ModernSpiderFoot(self._options())
        try:
            event, _ = core.cveInfo("CVE-2026-1234", sources="nist")
        finally:
            core.close()
        self.assertEqual(event, "VULNERABILITY_CVE_HIGH")
        fetch.assert_not_called()

    @patch.object(ModernSpiderFoot, "cachePut")
    @patch.object(ModernSpiderFoot, "cacheGet", return_value=None)
    @patch.object(ModernSpiderFoot, "fetchUrl")
    def test_falls_back_to_circl_when_nist_fails(self, fetch, _cache_get, _cache_put):
        fetch.side_effect = [
            {"code": "503", "content": None, "headers": {}, "realurl": "", "status": None},
            {"code": "200", "content": '{"cvss": 9.1, "summary": "Fallback"}', "headers": {}, "realurl": "", "status": None},
        ]
        core = ModernSpiderFoot(self._options())
        try:
            event, text = core.cveInfo("CVE-2026-1234", sources="nist,circl")
        finally:
            core.close()
        self.assertEqual(event, "VULNERABILITY_CVE_CRITICAL")
        self.assertIn("Fallback", text)
        self.assertEqual(fetch.call_count, 2)

    @patch.object(ModernSpiderFoot, "cacheGet", return_value=None)
    @patch.object(ModernSpiderFoot, "fetchUrl", return_value=None)
    def test_total_failure_returns_general_unknown(self, _fetch, _cache_get):
        core = ModernSpiderFoot(self._options())
        try:
            event, text = core.cveInfo("CVE-2026-1234", sources="nist")
        finally:
            core.close()
        self.assertEqual(event, "VULNERABILITY_GENERAL")
        self.assertIn("Score: Unknown", text)
        self.assertIn("Description: Unknown", text)

    @patch.object(ModernSpiderFoot, "cacheGet", side_effect=KeyboardInterrupt)
    def test_keyboard_interrupt_is_not_swallowed(self, _cache_get):
        core = ModernSpiderFoot(self._options())
        try:
            with self.assertRaises(KeyboardInterrupt):
                core.cveInfo("CVE-2026-1234", sources="nist")
        finally:
            core.close()


if __name__ == "__main__":
    unittest.main()

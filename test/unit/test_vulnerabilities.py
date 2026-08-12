import json
import unittest

from spiderfoot.vulnerabilities import (
    event_type,
    format_cve_result,
    parse_circl,
    parse_nvd_v2,
    severity_from_score,
)


class TestVulnerabilityHelpers(unittest.TestCase):

    def test_severity_boundaries(self):
        self.assertEqual(severity_from_score(0.0), "LOW")
        self.assertEqual(severity_from_score(3.9), "LOW")
        self.assertEqual(severity_from_score(4.0), "MEDIUM")
        self.assertEqual(severity_from_score(7.0), "HIGH")
        self.assertEqual(severity_from_score(9.0), "CRITICAL")
        self.assertIsNone(severity_from_score(10.1))
        self.assertIsNone(severity_from_score("bad"))

    def test_parses_nvd_v2_cvss31_and_english_description(self):
        payload = {
            "vulnerabilities": [{
                "cve": {
                    "descriptions": [
                        {"lang": "es", "value": "Descripcion"},
                        {"lang": "en", "value": "Example vulnerability"},
                    ],
                    "metrics": {
                        "cvssMetricV31": [{
                            "cvssData": {"baseScore": 9.8, "baseSeverity": "CRITICAL"}
                        }]
                    },
                }
            }]
        }
        info = parse_nvd_v2(json.dumps(payload))
        self.assertIsNotNone(info)
        self.assertEqual(info.score, 9.8)
        self.assertEqual(info.severity, "CRITICAL")
        self.assertEqual(info.description, "Example vulnerability")
        self.assertEqual(event_type(info), "VULNERABILITY_CVE_CRITICAL")

    def test_nvd_prefers_newest_available_metric_generation(self):
        payload = {
            "vulnerabilities": [{
                "cve": {
                    "descriptions": [{"lang": "en", "value": "Example"}],
                    "metrics": {
                        "cvssMetricV2": [{"cvssData": {"baseScore": 5.0}}],
                        "cvssMetricV40": [{"cvssData": {"baseScore": 8.1, "baseSeverity": "HIGH"}}],
                    },
                }
            }]
        }
        info = parse_nvd_v2(payload)
        self.assertEqual(info.score, 8.1)
        self.assertEqual(info.severity, "HIGH")

    def test_invalid_nvd_payload_returns_none(self):
        self.assertIsNone(parse_nvd_v2("not-json"))
        self.assertIsNone(parse_nvd_v2({"vulnerabilities": []}))
        self.assertIsNone(parse_nvd_v2(b"\xff"))

    def test_parses_legacy_circl_payload(self):
        info = parse_circl('{"cvss": 7.5, "summary": "A problem"}')
        self.assertEqual(info.score, 7.5)
        self.assertEqual(info.severity, "HIGH")
        self.assertEqual(info.description, "A problem")

    def test_format_preserves_spiderfoot_contract(self):
        info = parse_circl({"cvss": 4.2, "summary": "Description"})
        kind, text = format_cve_result("CVE-2026-1234", info)
        self.assertEqual(kind, "VULNERABILITY_CVE_MEDIUM")
        self.assertIn("CVE-2026-1234", text)
        self.assertIn("Score: 4.2", text)
        self.assertIn("Description: Description", text)

    def test_keyboard_interrupt_is_not_swallowed(self):
        class MappingThatInterrupts(dict):
            def get(self, key, default=None):
                raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            parse_nvd_v2(MappingThatInterrupts())


if __name__ == "__main__":
    unittest.main()

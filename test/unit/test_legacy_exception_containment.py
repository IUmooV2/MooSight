import unittest

from tools.verify_legacy_exception_containment import (
    find_legacy_exception_risks,
    method_is_overridden,
    verify_containment,
)


class TestLegacyExceptionContainment(unittest.TestCase):

    def test_finds_bare_and_base_exception_handlers(self):
        source = '''
class SpiderFoot:
    def one(self):
        try:
            run()
        except BaseException:
            pass

    def two(self):
        try:
            run()
        except:
            pass

    def safe(self):
        try:
            run()
        except ValueError:
            pass
'''
        risks = find_legacy_exception_risks(source)
        self.assertEqual([(r.method, r.kind) for r in risks], [
            ("one", "base-exception"),
            ("two", "bare-except"),
        ])

    def test_current_legacy_risks_are_contained_by_modern_runtime(self):
        result = verify_containment()
        self.assertTrue(result.risks)
        self.assertTrue(result.ok, result.uncontained)
        self.assertEqual(result.uncontained, ())

    def test_expected_legacy_methods_are_overridden(self):
        expected = {
            "optValueToData",
            "validIpNetwork",
            "resolveHost",
            "resolveIP",
            "resolveHost6",
            "parseCert",
            "cveInfo",
        }
        result = verify_containment()
        risky_methods = {risk.method for risk in result.risks}
        self.assertTrue(expected.issubset(risky_methods))
        for method in expected:
            with self.subTest(method=method):
                self.assertTrue(method_is_overridden(method))

    def test_unknown_method_is_not_reported_as_overridden(self):
        self.assertFalse(method_is_overridden("__definitely_not_a_real_method__"))


if __name__ == "__main__":
    unittest.main()

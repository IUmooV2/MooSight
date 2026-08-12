import tempfile
import unittest
from pathlib import Path

from tools.exception_audit import audit_repository, audit_source


class TestExceptionAudit(unittest.TestCase):

    def test_flags_bare_and_base_exception_handlers(self):
        source = """
try:
    run()
except:
    pass

try:
    run()
except BaseException:
    pass
"""
        findings = audit_source(source, "sample.py")
        kinds = [finding.kind for finding in findings]
        self.assertEqual(kinds, ["bare-except", "base-exception"])

    def test_exception_handler_is_review_only(self):
        findings = audit_source(
            "try:\n    run()\nexcept Exception:\n    pass\n",
            "sample.py",
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].kind, "broad-exception")

    def test_specific_handlers_are_not_flagged(self):
        source = """
try:
    run()
except (ValueError, TypeError):
    pass

try:
    run()
except OSError:
    pass
"""
        self.assertEqual(audit_source(source), [])

    def test_tuple_with_exception_is_review_only(self):
        findings = audit_source(
            "try:\n    run()\nexcept (ValueError, Exception):\n    pass\n",
            "sample.py",
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].kind, "broad-exception")

    def test_tuple_with_base_exception_is_blocking(self):
        findings = audit_source(
            "try:\n    run()\nexcept (ValueError, BaseException):\n    pass\n",
            "sample.py",
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].kind, "base-exception")

    def test_repository_scan_excludes_generated_dependency_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "good.py").write_text("try:\n    run()\nexcept BaseException:\n    pass\n", encoding="utf-8")
            excluded = root / ".venv"
            excluded.mkdir()
            (excluded / "ignored.py").write_text("try:\n    run()\nexcept:\n    pass\n", encoding="utf-8")

            findings = audit_repository(root)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].path, "good.py")
            self.assertEqual(findings[0].kind, "base-exception")

    def test_results_are_deterministic(self):
        source = """
try:
    a()
except Exception:
    pass
try:
    b()
except BaseException:
    pass
"""
        self.assertEqual(audit_source(source, "x.py"), audit_source(source, "x.py"))


if __name__ == "__main__":
    unittest.main()

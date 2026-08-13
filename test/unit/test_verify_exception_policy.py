import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.exception_audit import Finding
from tools.verify_exception_policy import PolicyResult, verify_exception_policy


class TestVerifyExceptionPolicy(unittest.TestCase):

    def test_policy_result_blocks_bare_and_base_exception(self):
        result = PolicyResult(
            findings=(
                Finding("x.py", 1, "broad-exception", "review"),
                Finding("x.py", 2, "base-exception", "block"),
            ),
            missing_files=(),
        )
        self.assertFalse(result.ok)
        self.assertEqual(len(result.blockers), 1)
        self.assertEqual(result.blockers[0].kind, "base-exception")

    def test_broad_exception_is_review_only(self):
        result = PolicyResult(
            findings=(Finding("x.py", 1, "broad-exception", "review"),),
            missing_files=(),
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.blockers, ())

    def test_missing_modern_file_fails_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = verify_exception_policy(Path(tmp))
            self.assertFalse(result.ok)
            self.assertTrue(result.missing_files)

    def test_policy_scans_only_declared_modern_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            modern_file = root / "modern.py"
            legacy_file = root / "legacy.py"
            modern_file.write_text("try:\n    run()\nexcept Exception:\n    pass\n", encoding="utf-8")
            legacy_file.write_text("try:\n    run()\nexcept BaseException:\n    pass\n", encoding="utf-8")

            with patch("tools.verify_exception_policy.MODERN_FILES", ("modern.py",)):
                result = verify_exception_policy(root)

            self.assertTrue(result.ok)
            self.assertEqual(len(result.findings), 1)
            self.assertEqual(result.findings[0].path, "modern.py")
            self.assertEqual(result.findings[0].kind, "broad-exception")

    def test_modern_base_exception_is_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "modern.py"
            path.write_text("try:\n    run()\nexcept BaseException:\n    pass\n", encoding="utf-8")

            with patch("tools.verify_exception_policy.MODERN_FILES", ("modern.py",)):
                result = verify_exception_policy(root)

            self.assertFalse(result.ok)
            self.assertEqual([f.kind for f in result.blockers], ["base-exception"])


if __name__ == "__main__":
    unittest.main()

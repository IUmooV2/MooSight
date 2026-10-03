import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.verify_modern_security import verify_modern_security


class TestModernSecurityPolicy(unittest.TestCase):

    def _verify_source(self, source: str):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "modern.py").write_text(source, encoding="utf-8")
            with patch("tools.verify_modern_security.MODERN_PYTHON_FILES", ("modern.py",)):
                return verify_modern_security(root)

    def test_clean_modern_file_passes(self):
        result = self._verify_source("value = 1\n")
        self.assertTrue(result.ok)
        self.assertEqual(result.blockers, ())

    def test_global_tls_context_override_blocks(self):
        result = self._verify_source(
            "import ssl\nssl._create_default_https_context = ssl._create_unverified_context\n"
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.blockers[0].rule, "TLS_GLOBAL_CONTEXT")

    def test_global_warning_suppression_blocks(self):
        result = self._verify_source(
            "import urllib3\nurllib3.disable_warnings()\n"
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.blockers[0].rule, "TLS_GLOBAL_WARNING_SUPPRESSION")

    def test_shell_true_blocks(self):
        result = self._verify_source(
            "import subprocess\nsubprocess.run(['echo', 'ok'], shell=True)\n"
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.blockers[0].rule, "SUBPROCESS_SHELL_TRUE")

    def test_verify_false_is_review_not_blocker(self):
        result = self._verify_source(
            "import requests\nrequests.get('https://example.com', verify=False)\n"
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.blockers, ())
        self.assertEqual(result.review_findings[0].rule, "TLS_VERIFY_FALSE")

    def test_missing_manifest_file_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("tools.verify_modern_security.MODERN_PYTHON_FILES", ("missing.py",)):
                result = verify_modern_security(Path(tmp))
        self.assertFalse(result.ok)
        self.assertEqual(result.missing_files, ("missing.py",))


if __name__ == "__main__":
    unittest.main()

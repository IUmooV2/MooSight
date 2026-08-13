import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.preflight import (
    Check,
    check_python,
    check_repository,
    exit_code,
    requirement_names,
)


class TestPreflight(unittest.TestCase):

    def test_python_check_accepts_supported_version(self):
        result = check_python((3, 10, 11))
        self.assertTrue(result.ok)

    def test_python_check_rejects_older_version(self):
        result = check_python((3, 9, 18))
        self.assertFalse(result.ok)

    def test_repository_check_reports_missing_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = check_repository(Path(tmp))
        self.assertFalse(result.ok)
        self.assertIn("sf.py", result.message)

    def test_requirement_names_ignores_comments_and_extracts_distribution_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "requirements.txt"
            path.write_text(
                "# comment\nrequests>=2.0\ncryptography<40\npackage[extra]==1.0\n\n",
                encoding="utf-8",
            )
            self.assertEqual(requirement_names(path), ["cryptography", "package", "requests"])

    def test_exit_code_only_fails_required_checks(self):
        self.assertEqual(exit_code([Check("ok", True, "ok")]), 0)
        self.assertEqual(exit_code([Check("warn", False, "optional", required=False)]), 0)
        self.assertEqual(exit_code([Check("fail", False, "required")]), 1)

    def test_requirement_names_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(requirement_names(Path(tmp) / "missing.txt"), [])

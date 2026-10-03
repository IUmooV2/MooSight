import tempfile
import textwrap
import unittest
from pathlib import Path

from tools.audit_security import audit


class TestSecurityAudit(unittest.TestCase):

    def _audit_source(self, source: str):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "sample.py"
            path.write_text(textwrap.dedent(source), encoding="utf-8")
            return audit(root)

    def test_detects_global_tls_context_override(self):
        findings = self._audit_source(
            """
            import ssl
            ssl._create_default_https_context = ssl._create_unverified_context
            """
        )
        self.assertIn("TLS_GLOBAL_CONTEXT", {item.rule for item in findings})

    def test_detects_global_tls_warning_suppression(self):
        findings = self._audit_source(
            """
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            """
        )
        self.assertIn("TLS_GLOBAL_WARNING_SUPPRESSION", {item.rule for item in findings})

    def test_detects_explicit_verify_false(self):
        findings = self._audit_source(
            """
            import requests
            requests.get('https://example.com', verify=False)
            """
        )
        self.assertIn("TLS_VERIFY_FALSE", {item.rule for item in findings})

    def test_detects_shell_true(self):
        findings = self._audit_source(
            """
            import subprocess
            subprocess.run('echo hello', shell=True)
            """
        )
        self.assertIn("SUBPROCESS_SHELL_TRUE", {item.rule for item in findings})

    def test_safe_patterns_do_not_trigger(self):
        findings = self._audit_source(
            """
            import requests
            import subprocess
            requests.get('https://example.com', verify=True)
            subprocess.run(['echo', 'hello'], shell=False)
            """
        )
        self.assertEqual(findings, [])

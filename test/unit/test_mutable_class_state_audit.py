import tempfile
import unittest
from pathlib import Path

from tools.audit_mutable_class_state import scan_repository, scan_source


class TestMutableClassStateAudit(unittest.TestCase):

    def test_detects_mutable_literals_and_constructor_calls(self):
        source = """
class Example:
    a = []
    b = {}
    c = set()
    d = list()
    e = tuple()
    f = 1
"""
        findings = scan_source(source)
        names = {finding.attribute for finding in findings}
        self.assertEqual(names, {"a", "b", "c", "d"})

    def test_detects_annotated_mutable_class_state(self):
        source = """
class Example:
    values: list[str] = []
"""
        findings = scan_source(source)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].attribute, "values")

    def test_ignores_instance_state_created_in_init(self):
        source = """
class Example:
    def __init__(self):
        self.values = []
"""
        self.assertEqual(scan_source(source), [])

    def test_repository_scan_skips_virtualenv_and_node_modules(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "good.py").write_text("class A:\n    values = []\n", encoding="utf-8")
            (root / ".venv").mkdir()
            (root / ".venv" / "ignored.py").write_text("class B:\n    values = []\n", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "ignored.py").write_text("class C:\n    values = []\n", encoding="utf-8")

            findings = scan_repository(root)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].path, "good.py")

    def test_findings_are_sorted_deterministically(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "z.py").write_text("class Z:\n    b = []\n", encoding="utf-8")
            (root / "a.py").write_text("class A:\n    a = {}\n", encoding="utf-8")

            findings = scan_repository(root)
            self.assertEqual([finding.path for finding in findings], ["a.py", "z.py"])

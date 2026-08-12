import logging
import sys
import unittest
from unittest.mock import patch

from spiderfoot.logger import SecretRedactionFilter


class TestSecretRedactionFilter(unittest.TestCase):

    def _record(self, message="message", args=(), exc_info=None):
        return logging.LogRecord(
            name="spiderfoot",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg=message,
            args=args,
            exc_info=exc_info,
        )

    def test_redacts_interpolated_message_arguments(self):
        record = self._record("Using proxy: %s", ("socks5://alice:secret@127.0.0.1:9050",))

        self.assertTrue(SecretRedactionFilter().filter(record))

        self.assertNotIn("alice", record.msg)
        self.assertNotIn("secret", record.msg)
        self.assertEqual(record.args, ())

    def test_redacts_exception_text_before_formatter_runs(self):
        try:
            raise RuntimeError("request failed token=supersecret")
        except RuntimeError:
            exc_info = sys.exc_info()

        record = self._record("request failed", exc_info=exc_info)

        SecretRedactionFilter().filter(record)

        self.assertIsNotNone(record.exc_text)
        self.assertNotIn("supersecret", record.exc_text)
        self.assertIn("token=[REDACTED]", record.exc_text)

    def test_preserves_traceback_structure_while_redacting_url_credentials(self):
        try:
            raise ValueError("https://alice:password@example.com/api?api_key=abc123")
        except ValueError:
            exc_info = sys.exc_info()

        record = self._record("boom", exc_info=exc_info)
        SecretRedactionFilter().filter(record)

        self.assertIn("ValueError", record.exc_text)
        self.assertNotIn("alice", record.exc_text)
        self.assertNotIn("password", record.exc_text)
        self.assertNotIn("abc123", record.exc_text)

    def test_traceback_render_failure_fails_closed(self):
        try:
            raise RuntimeError("password=hunter2")
        except RuntimeError:
            exc_info = sys.exc_info()

        record = self._record("boom", exc_info=exc_info)
        with patch.object(logging.Formatter, "formatException", side_effect=RuntimeError("renderer failed")):
            SecretRedactionFilter().filter(record)

        self.assertEqual(record.exc_text, "[REDACTED EXCEPTION]")
        self.assertNotIn("hunter2", record.exc_text)

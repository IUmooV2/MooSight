import ssl
import unittest
from unittest.mock import Mock, patch

import requests

from spiderfoot.modern_network_mixin import ModernNetworkMixin


class DummySpiderFoot(ModernNetworkMixin):
    def __init__(self, opts):
        self.opts = opts
        self.messages = []

    def debug(self, message):
        self.messages.append(("debug", message))

    def info(self, message):
        self.messages.append(("info", message))


class TestModernNetworkMixin(unittest.TestCase):

    def setUp(self):
        self.opts = {
            "_fetchtimeout": 5,
            "_useragent": "MooSight-Test",
            "_dnsserver": "",
            "_socks1type": "",
            "_socks2addr": "",
            "_socks3port": "",
            "_socks4user": "",
            "_socks5pwd": "",
        }

    def test_session_is_reused_per_instance(self):
        sf = DummySpiderFoot(self.opts)
        first = sf.getSession()
        second = sf.getSession()
        self.assertIs(first, second)
        self.assertIsInstance(first, requests.Session)
        sf.closeNetworkClient()

    def test_reset_rebuilds_session(self):
        sf = DummySpiderFoot(self.opts)
        first = sf.getSession()
        sf.resetNetworkClient()
        second = sf.getSession()
        self.assertIsNot(first, second)
        sf.closeNetworkClient()

    def test_remove_url_creds_uses_central_redaction(self):
        sf = DummySpiderFoot(self.opts)
        safe = sf.removeUrlCreds(
            "https://alice:secret@example.com/api?token=abc123&query=visible"
        )
        self.assertNotIn("alice", safe)
        self.assertNotIn("secret", safe)
        self.assertNotIn("abc123", safe)
        self.assertIn("query=visible", safe)

    def test_invalid_url_preserves_legacy_none_behavior(self):
        sf = DummySpiderFoot(self.opts)
        self.assertIsNone(sf.fetchUrl("file:///tmp/test"))
        self.assertTrue(any(level == "debug" for level, _ in sf.messages))
        sf.closeNetworkClient()

    @patch("spiderfoot.modern_network_mixin.create_tls_socket")
    def test_safe_ssl_socket_verifies_by_default(self, create_tls_socket):
        create_tls_socket.return_value = Mock()
        sf = DummySpiderFoot(self.opts)

        sf.safeSSLSocket("example.com", 443, 5)

        create_tls_socket.assert_called_once_with("example.com", 443, 5, verify=True)

    @patch("spiderfoot.modern_network_mixin.create_tls_socket")
    def test_safe_ssl_socket_allows_explicit_unverified_mode(self, create_tls_socket):
        create_tls_socket.return_value = Mock()
        sf = DummySpiderFoot(self.opts)

        sf.safeSSLSocket("example.com", 443, 5, verify=False)

        create_tls_socket.assert_called_once_with("example.com", 443, 5, verify=False)

    def test_mixin_does_not_modify_global_ssl_context(self):
        before = ssl._create_default_https_context
        sf = DummySpiderFoot(self.opts)
        sf.getSession()
        self.assertIs(ssl._create_default_https_context, before)
        sf.closeNetworkClient()

    def test_fetch_url_keeps_legacy_argument_names(self):
        sf = DummySpiderFoot(self.opts)
        service = Mock()
        service.fetch.return_value = {
            "code": "200",
            "status": None,
            "content": "hello",
            "headers": {},
            "realurl": "https://example.com/",
        }
        sf._modern_fetch_service = service

        result = sf.fetchUrl(
            "https://example.com/",
            cookies={"session": "secret"},
            timeout=7,
            useragent="UA",
            headers={"Accept": "text/plain"},
            postData="x=1",
            disableContentEncoding=True,
            sizeLimit=100,
            headOnly=False,
            verify=False,
        )

        self.assertEqual(result["code"], "200")
        service.fetch.assert_called_once_with(
            "https://example.com/",
            cookies={"session": "secret"},
            timeout=7,
            useragent="UA",
            headers={"Accept": "text/plain"},
            post_data="x=1",
            disable_content_encoding=True,
            size_limit=100,
            head_only=False,
            verify=False,
        )
        self.assertTrue(any(level == "info" and "HTTP 200" in message for level, message in sf.messages))

    def test_no_log_uses_debug_channel(self):
        sf = DummySpiderFoot(self.opts)
        service = Mock()
        service.fetch.return_value = {
            "code": "404",
            "status": None,
            "content": None,
            "headers": {},
            "realurl": "https://example.com/missing",
        }
        sf._modern_fetch_service = service

        sf.fetchUrl("https://example.com/missing", noLog=True)

        self.assertTrue(any(level == "debug" for level, _ in sf.messages))

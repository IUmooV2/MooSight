import socket
import ssl
import unittest
from unittest.mock import Mock, patch

from sflib import SpiderFoot as LegacySpiderFoot
from spiderfoot.modern_core import ModernSpiderFoot
from spiderfoot.modern_network_mixin import ModernNetworkMixin


class TestModernSpiderFootCore(unittest.TestCase):

    def _options(self):
        return {
            "_debug": False,
            "__logging": False,
            "_maxthreads": 3,
            "_fetchtimeout": 5,
            "_useragent": "MooSight-Test",
            "_dnsserver": "",
            "_socks1type": "",
            "_socks2addr": "",
            "_socks3port": "",
            "_socks4user": "",
            "_socks5pwd": "",
        }

    def test_facade_preserves_legacy_core_type_relationship(self):
        core = ModernSpiderFoot(self._options())
        try:
            self.assertIsInstance(core, LegacySpiderFoot)
            self.assertIsInstance(core, ModernNetworkMixin)
        finally:
            core.close()

    def test_modern_network_methods_win_in_mro(self):
        self.assertLess(
            ModernSpiderFoot.__mro__.index(ModernNetworkMixin),
            ModernSpiderFoot.__mro__.index(LegacySpiderFoot),
        )
        self.assertIs(ModernSpiderFoot.fetchUrl, ModernNetworkMixin.fetchUrl)
        self.assertIs(ModernSpiderFoot.getSession, ModernNetworkMixin.getSession)
        self.assertIs(ModernSpiderFoot.safeSSLSocket, ModernNetworkMixin.safeSSLSocket)
        self.assertIs(ModernSpiderFoot.removeUrlCreds, ModernNetworkMixin.removeUrlCreds)

    def test_construction_restores_process_https_context(self):
        before = ssl._create_default_https_context
        core = ModernSpiderFoot(self._options())
        try:
            self.assertIs(ssl._create_default_https_context, before)
        finally:
            core.close()

    def test_construction_restores_process_socket_resolver_functions(self):
        names = (
            "getaddrinfo",
            "getnameinfo",
            "getfqdn",
            "gethostbyname",
            "gethostbyname_ex",
            "gethostbyaddr",
        )
        before = {name: getattr(socket, name) for name in names if hasattr(socket, name)}
        options = self._options()
        options["_dnsserver"] = "1.1.1.1"

        core = ModernSpiderFoot(options)
        try:
            for name, function in before.items():
                with self.subTest(name=name):
                    self.assertIs(getattr(socket, name), function)
        finally:
            core.close()

    def test_network_client_is_lazy(self):
        core = ModernSpiderFoot(self._options())
        try:
            self.assertIsNone(core._modern_http_client)
            session = core.getSession()
            self.assertIsNotNone(session)
            self.assertIsNotNone(core._modern_http_client)
        finally:
            core.close()

    @patch("spiderfoot.modern_network_mixin.LegacyFetchService.fetch")
    def test_fetch_url_uses_modern_compatibility_stack(self, fetch):
        fetch.return_value = {
            "code": "200",
            "status": None,
            "content": "ok",
            "headers": {"content-type": "text/plain"},
            "realurl": "https://example.com/",
        }
        core = ModernSpiderFoot(self._options())
        try:
            result = core.fetchUrl("https://example.com/", noLog=True)
            self.assertEqual(result["code"], "200")
            self.assertEqual(result["content"], "ok")
            fetch.assert_called_once()
        finally:
            core.close()

    def test_close_releases_modern_client(self):
        core = ModernSpiderFoot(self._options())
        client = Mock()
        core._modern_http_client = client
        core._modern_fetch_service = Mock()

        core.close()

        client.close.assert_called_once_with()
        self.assertIsNone(core._modern_http_client)
        self.assertIsNone(core._modern_fetch_service)

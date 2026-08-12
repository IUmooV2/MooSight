import socket
import ssl
import tempfile
import unittest
from pathlib import Path
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

    def test_constructor_does_not_call_side_effectful_legacy_constructor(self):
        with patch.object(LegacySpiderFoot, "__init__", side_effect=AssertionError("legacy init called")) as legacy_init:
            core = ModernSpiderFoot(self._options())
            try:
                legacy_init.assert_not_called()
            finally:
                core.close()

    def test_options_are_deep_copied(self):
        options = self._options()
        options["nested"] = {"value": [1]}
        core = ModernSpiderFoot(options)
        try:
            options["nested"]["value"].append(2)
            self.assertEqual(core.opts["nested"]["value"], [1])
        finally:
            core.close()

    def test_constructor_rejects_non_dict_options(self):
        with self.assertRaises(TypeError):
            ModernSpiderFoot(None)

    def test_construction_preserves_process_https_context(self):
        before = ssl._create_default_https_context
        core = ModernSpiderFoot(self._options())
        try:
            self.assertIs(ssl._create_default_https_context, before)
        finally:
            core.close()

    def test_construction_preserves_process_socket_resolver_functions(self):
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

    def test_option_plain_string_is_returned_unchanged(self):
        core = ModernSpiderFoot(self._options())
        try:
            self.assertEqual(core.optValueToData("plain-value"), "plain-value")
        finally:
            core.close()

    def test_option_file_is_read_as_utf8(self):
        core = ModernSpiderFoot(self._options())
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "option.txt"
                path.write_text("MooSight ✓", encoding="utf-8")
                self.assertEqual(core.optValueToData(f"@{path}"), "MooSight ✓")
        finally:
            core.close()

    @patch.object(ModernSpiderFoot, "fetchUrl")
    def test_option_url_uses_modern_fetch_stack(self, fetch):
        fetch.return_value = {
            "code": "200",
            "status": None,
            "content": "remote-value",
            "headers": {},
            "realurl": "https://example.com/config.txt",
        }
        core = ModernSpiderFoot(self._options())
        try:
            self.assertEqual(
                core.optValueToData("https://example.com/config.txt?token=secret"),
                "remote-value",
            )
            fetch.assert_called_once()
            kwargs = fetch.call_args.kwargs
            self.assertTrue(kwargs["verify"])
            self.assertTrue(kwargs["noLog"])
            self.assertEqual(kwargs["timeout"], 5)
            self.assertEqual(kwargs["useragent"], "MooSight-Test")
        finally:
            core.close()

    @patch.object(ModernSpiderFoot, "fetchUrl")
    def test_option_url_decodes_utf8_bytes(self, fetch):
        fetch.return_value = {
            "code": "200",
            "status": None,
            "content": "MooSight ✓".encode("utf-8"),
            "headers": {},
            "realurl": "https://example.com/config.txt",
        }
        core = ModernSpiderFoot(self._options())
        try:
            self.assertEqual(core.optValueToData("https://example.com/config.txt"), "MooSight ✓")
        finally:
            core.close()

    @patch.object(ModernSpiderFoot, "fetchUrl")
    def test_option_url_failure_returns_none(self, fetch):
        fetch.return_value = None
        core = ModernSpiderFoot(self._options())
        try:
            self.assertIsNone(core.optValueToData("https://example.com/config.txt"))
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

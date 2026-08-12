import unittest

from spiderfoot.config import NetworkConfig, RuntimeConfig


class TestTypedConfiguration(unittest.TestCase):

    def test_network_config_reads_legacy_defaults(self):
        config = NetworkConfig.from_legacy({})
        self.assertEqual(config.timeout, 5)
        self.assertEqual(config.user_agent, "SpiderFoot")
        self.assertFalse(config.proxy_enabled)
        self.assertIsNone(config.proxy_url())

    def test_network_config_builds_socks5_proxy_with_escaped_credentials(self):
        config = NetworkConfig.from_legacy({
            "_socks1type": "5",
            "_socks2addr": "127.0.0.1",
            "_socks3port": "1080",
            "_socks4user": "user name",
            "_socks5pwd": "p@ss/word",
        })
        self.assertTrue(config.proxy_enabled)
        self.assertEqual(
            config.proxy_url(),
            "socks5://user%20name:p%40ss%2Fword@127.0.0.1:1080",
        )

    def test_tor_uses_remote_dns_scheme(self):
        config = NetworkConfig.from_legacy({
            "_socks1type": "TOR",
            "_socks2addr": "127.0.0.1",
            "_socks3port": 9050,
        })
        self.assertEqual(config.proxy_url(), "socks5h://127.0.0.1:9050")

    def test_invalid_proxy_type_is_rejected(self):
        with self.assertRaises(ValueError):
            NetworkConfig.from_legacy({"_socks1type": "INVALID"})

    def test_invalid_proxy_port_is_rejected(self):
        for value in (0, 65536, "not-a-port"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    NetworkConfig.from_legacy({"_socks3port": value})

    def test_invalid_timeout_is_rejected(self):
        for value in (0, -1, "abc"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    NetworkConfig.from_legacy({"_fetchtimeout": value})

    def test_runtime_config_reads_core_values(self):
        config = RuntimeConfig.from_legacy({
            "_debug": True,
            "__logging": False,
            "_maxthreads": "8",
            "_fetchtimeout": 12,
        })
        self.assertTrue(config.debug)
        self.assertFalse(config.logging_enabled)
        self.assertEqual(config.max_threads, 8)
        self.assertEqual(config.network.timeout, 12)

    def test_runtime_config_rejects_invalid_thread_count(self):
        for value in (0, -2, "abc"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    RuntimeConfig.from_legacy({"_maxthreads": value})

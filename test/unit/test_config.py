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

    def test_proxy_types_receive_legacy_default_ports(self):
        expected = {
            "4": (1080, "socks4://proxy.example:1080"),
            "5": (1080, "socks5://proxy.example:1080"),
            "HTTP": (8080, "http://proxy.example:8080"),
            "TOR": (9050, "socks5h://proxy.example:9050"),
        }
        for proxy_type, (port, url) in expected.items():
            with self.subTest(proxy_type=proxy_type):
                config = NetworkConfig.from_legacy({
                    "_socks1type": proxy_type,
                    "_socks2addr": "proxy.example",
                })
                self.assertEqual(config.proxy_port, port)
                self.assertTrue(config.proxy_enabled)
                self.assertEqual(config.proxy_url(), url)

    def test_proxy_routing_bypasses_local_and_proxy_targets(self):
        config = NetworkConfig(proxy_type="5", proxy_host="proxy.example", proxy_port=1080)
        bypassed = (
            "http://127.0.0.1:5001/",
            "http://10.0.0.5/",
            "http://169.254.1.2/",
            "http://localhost/",
            "http://service.local/",
            "https://proxy.example/",
        )
        for url in bypassed:
            with self.subTest(url=url):
                self.assertFalse(config.should_proxy_url(url))

        self.assertTrue(config.should_proxy_url("https://example.com/path"))
        self.assertTrue(config.should_proxy_url("https://8.8.8.8/"))

    def test_proxy_routing_rejects_invalid_urls_and_disabled_proxy(self):
        self.assertFalse(NetworkConfig().should_proxy_url("https://example.com"))
        config = NetworkConfig(proxy_type="5", proxy_host="proxy.example", proxy_port=1080)
        for value in ("", "not-a-url", "file:///tmp/test"):
            with self.subTest(value=value):
                self.assertFalse(config.should_proxy_url(value))

    def test_proxy_type_requires_host(self):
        for proxy_type in ("4", "5", "HTTP", "TOR"):
            with self.subTest(proxy_type=proxy_type):
                with self.assertRaises(ValueError):
                    NetworkConfig.from_legacy({"_socks1type": proxy_type})

    def test_proxy_password_requires_username(self):
        with self.assertRaises(ValueError):
            NetworkConfig.from_legacy({
                "_socks1type": "5",
                "_socks2addr": "127.0.0.1",
                "_socks5pwd": "secret",
            })

    def test_proxy_username_without_password_is_supported(self):
        config = NetworkConfig.from_legacy({
            "_socks1type": "HTTP",
            "_socks2addr": "proxy.example",
            "_socks4user": "user name",
        })
        self.assertEqual(config.proxy_url(), "http://user%20name@proxy.example:8080")

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

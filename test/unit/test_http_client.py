import unittest
from unittest.mock import Mock, patch

from spiderfoot.config import NetworkConfig
from spiderfoot.http_client import HttpClient
from spiderfoot.network import NetworkResult, NetworkState


class TestHttpClient(unittest.TestCase):

    def test_requires_network_config(self):
        with self.assertRaises(TypeError):
            HttpClient({})

    def test_from_legacy_builds_validated_config(self):
        client = HttpClient.from_legacy({
            "_fetchtimeout": 7,
            "_useragent": "MooSight-Test",
            "_socks1type": "",
            "_socks2addr": "",
            "_socks3port": "",
            "_socks4user": "",
            "_socks5pwd": "",
        })
        self.assertEqual(client.config.timeout, 7)
        self.assertEqual(client.config.user_agent, "MooSight-Test")
        client.close()

    @patch("spiderfoot.http_client.request_with_config")
    def test_get_reuses_client_session(self, request_mock):
        request_mock.return_value = NetworkResult(NetworkState.SUCCESS, status_code=200)
        client = HttpClient(NetworkConfig())

        result = client.get("https://example.com/")

        self.assertTrue(result.ok)
        self.assertIs(request_mock.call_args.kwargs["session"], client.session)
        client.close()

    @patch("spiderfoot.http_client.request_with_config")
    def test_post_passes_data_without_changing_method(self, request_mock):
        request_mock.return_value = NetworkResult(NetworkState.SUCCESS, status_code=200)
        client = HttpClient(NetworkConfig())

        client.post("https://example.com/", data="a=1")

        args = request_mock.call_args.args
        kwargs = request_mock.call_args.kwargs
        self.assertEqual(args[1], "POST")
        self.assertEqual(kwargs["data"], "a=1")
        client.close()

    @patch("spiderfoot.http_client.build_session")
    @patch("spiderfoot.http_client.request_with_config")
    def test_local_target_bypasses_configured_proxy(self, request_mock, build_session):
        request_mock.return_value = NetworkResult(NetworkState.SUCCESS, status_code=200)
        direct_session = Mock()
        build_session.return_value = direct_session
        client = HttpClient(NetworkConfig(proxy_type="5", proxy_host="proxy.example", proxy_port=1080))

        client.get("http://127.0.0.1:5001/")

        self.assertIs(request_mock.call_args.kwargs["session"], direct_session)
        direct_session.close.assert_called_once_with()
        client.close()

    @patch("spiderfoot.http_client.build_session")
    @patch("spiderfoot.http_client.request_with_config")
    def test_public_target_keeps_configured_proxy_session(self, request_mock, build_session):
        request_mock.return_value = NetworkResult(NetworkState.SUCCESS, status_code=200)
        client = HttpClient(NetworkConfig(proxy_type="5", proxy_host="proxy.example", proxy_port=1080))

        client.get("https://example.com/")

        build_session.assert_not_called()
        self.assertIs(request_mock.call_args.kwargs["session"], client.session)
        client.close()

    @patch("spiderfoot.http_client.build_session")
    @patch("spiderfoot.http_client.request_with_config", side_effect=RuntimeError("boom"))
    def test_direct_session_closes_when_request_raises(self, request_mock, build_session):
        direct_session = Mock()
        build_session.return_value = direct_session
        client = HttpClient(NetworkConfig(proxy_type="5", proxy_host="proxy.example", proxy_port=1080))

        with self.assertRaises(RuntimeError):
            client.get("http://localhost/")

        direct_session.close.assert_called_once_with()
        client.close()

    @patch("spiderfoot.http_client.to_legacy_result")
    @patch("spiderfoot.http_client.request_with_config")
    def test_request_legacy_uses_normalized_result_as_source_of_truth(self, request_mock, legacy_mock):
        normalized = NetworkResult(
            NetworkState.RATE_LIMITED,
            status_code=429,
            url="https://example.com/",
            content=b"slow down",
        )
        request_mock.return_value = normalized
        legacy_mock.return_value = {
            "code": "429",
            "status": "rate_limited",
            "content": "slow down",
            "headers": {},
            "realurl": "https://example.com/",
        }
        client = HttpClient(NetworkConfig())

        result = client.request_legacy("GET", "https://example.com/")

        self.assertEqual(result["code"], "429")
        self.assertEqual(result["status"], "rate_limited")
        legacy_mock.assert_called_once_with(
            normalized,
            requested_url="https://example.com/",
            disable_content_encoding=False,
        )
        client.close()

    def test_context_manager_closes_session(self):
        client = HttpClient(NetworkConfig())
        client.session.close = Mock()

        with client as active:
            self.assertIs(active, client)

        client.session.close.assert_called_once_with()

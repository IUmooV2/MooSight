import unittest
from unittest.mock import Mock

from spiderfoot.config import NetworkConfig
from spiderfoot.http_client import HttpClient
from spiderfoot.legacy_fetch import LegacyFetchService
from spiderfoot.network import NetworkResult, NetworkState


class TestLegacyFetchService(unittest.TestCase):

    def _service(self):
        client = HttpClient(NetworkConfig(timeout=5, user_agent="MooSight-Test"))
        client.request = Mock()
        client.head = Mock()
        return LegacyFetchService(client)

    def test_rejects_non_http_url(self):
        service = self._service()
        with self.assertRaises(ValueError):
            service.fetch("file:///tmp/test")

    def test_builds_user_agent_and_custom_headers(self):
        service = self._service()
        service.client.request.return_value = NetworkResult(
            state=NetworkState.SUCCESS,
            status_code=200,
            url="https://example.com/",
            content=b"ok",
            headers={},
        )

        service.fetch(
            "https://example.com/",
            useragent="UA-1",
            headers={"Accept": "application/json"},
        )

        kwargs = service.client.request.call_args.kwargs
        self.assertEqual(kwargs["headers"]["User-Agent"], "UA-1")
        self.assertEqual(kwargs["headers"]["Accept"], "application/json")

    def test_post_data_selects_post_even_when_empty_bytes(self):
        service = self._service()
        service.client.request.return_value = NetworkResult(
            state=NetworkState.SUCCESS,
            status_code=200,
            url="https://example.com/",
            content=b"ok",
            headers={},
        )

        service.fetch("https://example.com/", post_data=b"")

        self.assertEqual(service.client.request.call_args.args[0], "POST")

    def test_head_only_does_not_issue_get(self):
        service = self._service()
        service.client.head.return_value = NetworkResult(
            state=NetworkState.SUCCESS,
            status_code=200,
            url="https://example.com/",
            content=None,
            headers={"content-length": "123"},
        )

        result = service.fetch("https://example.com/", head_only=True)

        self.assertEqual(result["code"], "200")
        service.client.request.assert_not_called()

    def test_size_limit_stops_after_large_head_response(self):
        service = self._service()
        service.client.head.return_value = NetworkResult(
            state=NetworkState.SUCCESS,
            status_code=200,
            url="https://example.com/",
            content=None,
            headers={"content-length": "1000"},
        )

        result = service.fetch("https://example.com/", size_limit=100)

        self.assertEqual(result["code"], "200")
        service.client.request.assert_not_called()

    def test_invalid_content_length_falls_back_to_get(self):
        service = self._service()
        service.client.head.return_value = NetworkResult(
            state=NetworkState.SUCCESS,
            status_code=200,
            url="https://example.com/",
            content=None,
            headers={"content-length": "unknown"},
        )
        service.client.request.return_value = NetworkResult(
            state=NetworkState.SUCCESS,
            status_code=200,
            url="https://example.com/",
            content=b"ok",
            headers={},
        )

        service.fetch("https://example.com/", size_limit=100)
        service.client.request.assert_called_once()

    def test_refresh_header_follows_relative_url(self):
        service = self._service()
        service.client.request.side_effect = [
            NetworkResult(
                state=NetworkState.SUCCESS,
                status_code=200,
                url="https://example.com/start",
                content=b"first",
                headers={"refresh": "0; URL=/next"},
            ),
            NetworkResult(
                state=NetworkState.SUCCESS,
                status_code=200,
                url="https://example.com/next",
                content=b"second",
                headers={},
            ),
        ]

        result = service.fetch("https://example.com/start")

        self.assertEqual(result["content"], "second")
        second_call = service.client.request.call_args_list[1]
        self.assertEqual(second_call.args[1], "https://example.com/next")

    def test_refresh_redirects_are_bounded(self):
        service = self._service()
        service.client.request.return_value = NetworkResult(
            state=NetworkState.SUCCESS,
            status_code=200,
            url="https://example.com/loop",
            content=b"body",
            headers={"refresh": "0;url=/loop"},
        )

        result = service.fetch("https://example.com/loop", max_refresh_redirects=2)

        self.assertEqual(result["code"], "200")
        self.assertEqual(service.client.request.call_count, 3)

    def test_diagnostics_redact_proxy_cookie_and_auth_header(self):
        config = NetworkConfig(
            proxy_type="5",
            proxy_host="127.0.0.1",
            proxy_port=9050,
            proxy_username="alice",
            proxy_password="secret",
        )
        service = LegacyFetchService(HttpClient(config))
        metadata = service.diagnostic_metadata(
            url="https://example.com/?token=abc",
            timeout=5,
            headers={"Authorization": "Bearer xyz", "Accept": "text/plain"},
            cookies={"sessionid": "cookie-secret"},
        )

        rendered = repr(metadata)
        self.assertNotIn("alice", rendered)
        self.assertNotIn("secret", rendered)
        self.assertNotIn("abc", rendered)
        self.assertNotIn("xyz", rendered)
        self.assertNotIn("cookie-secret", rendered)
        service.close()

    def test_negative_size_limit_is_rejected_before_request(self):
        service = self._service()
        with self.assertRaises(ValueError):
            service.fetch("https://example.com/", size_limit=-1)
        service.client.head.assert_not_called()
        service.client.request.assert_not_called()

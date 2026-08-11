import ssl
import unittest
import warnings
from unittest.mock import Mock

import requests
import urllib3

from spiderfoot.network import (
    NetworkResult,
    NetworkState,
    ScopedInsecureRequestWarnings,
    build_session,
    classify_exception,
    classify_http_status,
    request_url,
)


class TestNetworkPrimitives(unittest.TestCase):

    def test_http_status_classification(self):
        expectations = {
            200: NetworkState.SUCCESS,
            302: NetworkState.SUCCESS,
            401: NetworkState.AUTH_REQUIRED,
            403: NetworkState.BLOCKED,
            404: NetworkState.NOT_FOUND,
            429: NetworkState.RATE_LIMITED,
            500: NetworkState.INVALID_RESPONSE,
            None: NetworkState.INDETERMINATE,
        }
        for status, expected in expectations.items():
            with self.subTest(status=status):
                self.assertEqual(classify_http_status(status), expected)

    def test_exception_classification(self):
        values = [
            (requests.exceptions.SSLError("bad tls"), NetworkState.TLS_ERROR),
            (requests.exceptions.Timeout("slow"), NetworkState.TIMEOUT),
            (requests.exceptions.ConnectionError("down"), NetworkState.NETWORK_ERROR),
            (ValueError("unexpected"), NetworkState.INDETERMINATE),
        ]
        for exc, expected in values:
            with self.subTest(exc=type(exc).__name__):
                self.assertEqual(classify_exception(exc), expected)

    def test_network_result_ok_only_for_success(self):
        self.assertTrue(NetworkResult(NetworkState.SUCCESS).ok)
        self.assertFalse(NetworkResult(NetworkState.NOT_FOUND).ok)
        self.assertFalse(NetworkResult(NetworkState.INDETERMINATE).ok)

    def test_build_session_scopes_proxy_to_session(self):
        session = build_session("socks5://127.0.0.1:9050")
        self.assertIsInstance(session, requests.Session)
        self.assertEqual(session.proxies["http"], "socks5://127.0.0.1:9050")
        self.assertEqual(session.proxies["https"], "socks5://127.0.0.1:9050")

    def test_build_session_does_not_mutate_default_ssl_context(self):
        before = ssl._create_default_https_context
        build_session()
        self.assertIs(ssl._create_default_https_context, before)

    def test_insecure_warning_suppression_is_scoped(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            warnings.warn("before", urllib3.exceptions.InsecureRequestWarning)
            with ScopedInsecureRequestWarnings():
                warnings.warn("inside", urllib3.exceptions.InsecureRequestWarning)
            warnings.warn("after", urllib3.exceptions.InsecureRequestWarning)

        messages = [str(item.message) for item in caught]
        self.assertIn("before", messages)
        self.assertNotIn("inside", messages)
        self.assertIn("after", messages)

    def _mock_session_response(self, status=200, content=b"ok", url="https://example.com/"):
        session = requests.Session()
        response = Mock()
        response.status_code = status
        response.content = content
        response.url = url
        response.headers = {"Content-Type": "text/plain"}
        session.request = Mock(return_value=response)
        return session

    def test_request_url_verifies_tls_by_default(self):
        session = self._mock_session_response()
        result = request_url(session, "GET", "https://example.com/")

        self.assertEqual(result.state, NetworkState.SUCCESS)
        self.assertTrue(result.tls_verified)
        self.assertEqual(result.content, b"ok")
        self.assertTrue(session.request.call_args.kwargs["verify"])

    def test_request_url_allows_explicit_unverified_request_without_global_tls_mutation(self):
        session = self._mock_session_response()
        before = ssl._create_default_https_context

        result = request_url(session, "GET", "https://example.com/", verify=False)

        self.assertEqual(result.state, NetworkState.SUCCESS)
        self.assertFalse(result.tls_verified)
        self.assertFalse(session.request.call_args.kwargs["verify"])
        self.assertIs(ssl._create_default_https_context, before)

    def test_request_url_distinguishes_timeout_from_not_found(self):
        session = requests.Session()
        session.request = Mock(side_effect=requests.exceptions.Timeout("slow"))

        result = request_url(session, "GET", "https://example.com/")

        self.assertEqual(result.state, NetworkState.TIMEOUT)
        self.assertNotEqual(result.state, NetworkState.NOT_FOUND)

    def test_request_url_redacts_credentials_from_returned_url(self):
        session = requests.Session()
        session.request = Mock(side_effect=requests.exceptions.ConnectionError("offline"))

        result = request_url(
            session,
            "GET",
            "https://alice:secret@example.com/api?token=abc123&query=safe",
        )

        self.assertEqual(result.state, NetworkState.NETWORK_ERROR)
        self.assertNotIn("alice", result.url)
        self.assertNotIn("secret", result.url)
        self.assertNotIn("abc123", result.url)
        self.assertIn("query=safe", result.url)

    def test_request_url_classifies_rate_limit(self):
        session = self._mock_session_response(status=429, content=b"slow down")
        result = request_url(session, "GET", "https://example.com/")
        self.assertEqual(result.state, NetworkState.RATE_LIMITED)
        self.assertEqual(result.status_code, 429)

    def test_request_url_marks_oversized_response_invalid(self):
        session = self._mock_session_response(content=b"0123456789")
        result = request_url(session, "GET", "https://example.com/", size_limit=4)
        self.assertEqual(result.state, NetworkState.INVALID_RESPONSE)
        self.assertIsNone(result.content)

    def test_request_url_rejects_unsupported_method(self):
        session = requests.Session()
        with self.assertRaises(ValueError):
            request_url(session, "TRACE", "https://example.com/")

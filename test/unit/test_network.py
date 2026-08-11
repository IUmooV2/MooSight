import ssl
import unittest
import warnings

import requests
import urllib3

from spiderfoot.network import (
    NetworkResult,
    NetworkState,
    ScopedInsecureRequestWarnings,
    build_session,
    classify_exception,
    classify_http_status,
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

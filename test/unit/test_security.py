import unittest

from spiderfoot.security import (
    is_sensitive_name,
    redact_cookies,
    redact_headers,
    redact_mapping,
    redact_proxy,
    redact_url,
)


class TestSecurityRedaction(unittest.TestCase):

    def test_sensitive_names_are_case_insensitive(self):
        for name in ("Authorization", "API_KEY", "access_token", "password", "client_secret"):
            with self.subTest(name=name):
                self.assertTrue(is_sensitive_name(name))
        self.assertFalse(is_sensitive_name("user_agent"))

    def test_redact_headers_hides_auth_and_cookie_values(self):
        headers = {
            "Authorization": "Bearer super-secret-token",
            "Cookie": "sessionid=abcdef",
            "Accept": "application/json",
        }
        result = redact_headers(headers)
        self.assertEqual(result["Authorization"], "[REDACTED]")
        self.assertEqual(result["Cookie"], "[REDACTED]")
        self.assertEqual(result["Accept"], "application/json")
        self.assertNotIn("super-secret-token", repr(result))
        self.assertNotIn("abcdef", repr(result))

    def test_redact_proxy_removes_credentials(self):
        value = redact_proxy("socks5://alice:password123@127.0.0.1:9050")
        self.assertEqual(value, "socks5://[REDACTED]@127.0.0.1:9050")
        self.assertNotIn("alice", value)
        self.assertNotIn("password123", value)

    def test_redact_url_hides_userinfo_and_sensitive_query_values(self):
        value = redact_url(
            "https://alice:secret@example.com/api?token=abc123&query=public&api_key=xyz"
        )
        self.assertNotIn("alice", value)
        self.assertNotIn("secret", value)
        self.assertNotIn("abc123", value)
        self.assertNotIn("xyz", value)
        self.assertIn("query=public", value)
        self.assertIn("token=%5BREDACTED%5D", value)

    def test_redact_cookies_keeps_names_but_not_values(self):
        value = redact_cookies({"sessionid": "abc", "theme": "dark"})
        self.assertIn("sessionid=[REDACTED]", value)
        self.assertIn("theme=[REDACTED]", value)
        self.assertNotIn("abc", value)
        self.assertNotIn("dark", value)

    def test_redact_mapping_hides_secret_like_keys(self):
        result = redact_mapping({"api_token": "abc", "timeout": 30})
        self.assertEqual(result["api_token"], "[REDACTED]")
        self.assertEqual(result["timeout"], 30)

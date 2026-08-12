import socket
import ssl
import unittest
from unittest.mock import Mock, patch

from spiderfoot.tls import TLSSettings, create_tls_context, open_tcp_socket, open_tls_socket


class TestTLSHelpers(unittest.TestCase):

    def test_verified_context_is_default(self):
        context = create_tls_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_unverified_context_is_explicit_and_local(self):
        before = ssl._create_default_https_context
        context = create_tls_context(verify=False)
        self.assertEqual(context.verify_mode, ssl.CERT_NONE)
        self.assertFalse(context.check_hostname)
        self.assertIs(ssl._create_default_https_context, before)

    def test_tls_settings_validate_timeout(self):
        with self.assertRaises(ValueError):
            TLSSettings(timeout=0)

    def test_open_tcp_socket_validates_host_and_port(self):
        with self.assertRaises(ValueError):
            open_tcp_socket('', 443)
        with self.assertRaises(ValueError):
            open_tcp_socket('example.com', 0)
        with self.assertRaises(ValueError):
            open_tcp_socket('example.com', 70000)

    @patch('spiderfoot.tls.socket.create_connection')
    def test_open_tcp_socket_uses_bounded_timeout(self, create_connection):
        fake = Mock(spec=socket.socket)
        create_connection.return_value = fake

        result = open_tcp_socket('example.com', 443, timeout=4.5)

        self.assertIs(result, fake)
        create_connection.assert_called_once_with(('example.com', 443), timeout=4.5)

    @patch('spiderfoot.tls.open_tcp_socket')
    def test_open_tls_socket_wraps_socket_with_server_hostname(self, open_socket):
        raw = Mock(spec=socket.socket)
        open_socket.return_value = raw
        context = Mock(spec=ssl.SSLContext)
        wrapped = Mock(spec=ssl.SSLSocket)
        context.wrap_socket.return_value = wrapped

        result = open_tls_socket(
            'example.com',
            443,
            settings=TLSSettings(verify=True, timeout=3, server_hostname='example.com'),
            context=context,
        )

        self.assertIs(result, wrapped)
        open_socket.assert_called_once_with('example.com', 443, timeout=3)
        context.wrap_socket.assert_called_once_with(raw, server_hostname='example.com')

    @patch('spiderfoot.tls.open_tcp_socket')
    def test_open_tls_socket_closes_raw_socket_on_handshake_failure(self, open_socket):
        raw = Mock(spec=socket.socket)
        open_socket.return_value = raw
        context = Mock(spec=ssl.SSLContext)
        context.wrap_socket.side_effect = ssl.SSLError('handshake failed')

        with self.assertRaises(ssl.SSLError):
            open_tls_socket('example.com', 443, context=context)

        raw.close.assert_called_once_with()

    def test_open_tls_socket_rejects_wrong_settings_type(self):
        with self.assertRaises(TypeError):
            open_tls_socket('example.com', 443, settings={})

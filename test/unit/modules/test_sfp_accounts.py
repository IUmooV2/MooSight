import pytest
import unittest
from unittest.mock import Mock

from modules.sfp_accounts import sfp_accounts
from sflib import SpiderFoot


@pytest.mark.usefixtures
class TestModuleAccounts(unittest.TestCase):

    def test_opts(self):
        module = sfp_accounts()
        self.assertEqual(len(module.opts), len(module.optdescs))

    def test_setup(self):
        sf = SpiderFoot(self.default_options)
        module = sfp_accounts()
        module.setup(sf, dict())

    def test_watchedEvents_should_return_list(self):
        module = sfp_accounts()
        self.assertIsInstance(module.watchedEvents(), list)

    def test_producedEvents_should_return_list(self):
        module = sfp_accounts()
        self.assertIsInstance(module.producedEvents(), list)

    def test_normalize_username_preserves_periods_and_strips_quotes(self):
        self.assertEqual(sfp_accounts._normalize_username('  "sonrie.99"  '), 'sonrie.99')

    def test_normalize_username_rejects_path_like_and_control_input(self):
        invalid = [None, '', '   ', 'name/other', 'name\\other', 'name\nother', 'name\tother']
        for value in invalid:
            with self.subTest(value=value):
                self.assertIsNone(sfp_accounts._normalize_username(value))

    def test_host_only_accepts_parseable_hostname(self):
        self.assertEqual(sfp_accounts._host('https://instagram.com/example'), 'instagram.com')
        self.assertEqual(sfp_accounts._host('not-a-url'), '')

    def test_generate_permutations_is_conservative_and_deterministic(self):
        module = sfp_accounts()
        self.assertEqual(
            module.generatePermutations('sample'),
            ['-sample', '_sample', 'sample-', 'sample_']
        )

    def test_checkSites_rejects_invalid_username_without_network_requests(self):
        module = sfp_accounts()
        self.assertEqual(module.checkSites('bad/name', []), [])

    def _module_for_site_check(self, response):
        module = sfp_accounts()
        module.sf = Mock()
        module.sf.fetchUrl.return_value = response
        module.lock = __import__('threading').Lock()
        module.siteResults = {}
        module.opts = {
            '_fetchtimeout': 5,
            '_useragent': 'MooSight-Test',
            'musthavename': True,
            'allow_insecure_tls': False,
        }
        return module

    def test_check_site_verifies_tls_by_default_and_honors_dataset_headers(self):
        module = self._module_for_site_check({
            'content': '{"id":1}',
            'code': '200',
            'headers': {'Content-Type': 'application/json'},
        })
        site = {
            'name': 'Example',
            'cat': 'social',
            'uri_check': 'https://example.com/api/{account}',
            'uri_pretty': 'https://example.com/{account}',
            'headers': {'Accept': 'application/json', 'X-User': '{account}'},
            'e_code': 200,
            'm_code': 404,
            'e_string': '"id":',
            'm_string': 'not found',
        }

        module.checkSite('alice', site)

        kwargs = module.sf.fetchUrl.call_args.kwargs
        self.assertTrue(kwargs['verify'])
        self.assertEqual(kwargs['headers']['Accept'], 'application/json')
        self.assertEqual(kwargs['headers']['X-User'], 'alice')
        self.assertTrue(any(module.siteResults.values()))

    def test_check_site_formats_account_in_post_body(self):
        module = self._module_for_site_check({
            'content': '"id":123',
            'code': '200',
            'headers': {'content-type': 'application/json'},
        })
        site = {
            'name': 'Post Example',
            'cat': 'social',
            'uri_check': 'https://example.com/api',
            'post_body': '{"username":"{account}"}',
            'e_code': 200,
            'm_code': 404,
            'e_string': '"id":',
            'm_string': 'not found',
        }

        module.checkSite('alice', site)

        self.assertEqual(module.sf.fetchUrl.call_args.kwargs['postData'], '{"username":"alice"}')

    def test_positive_dataset_fingerprint_does_not_require_literal_username(self):
        module = self._module_for_site_check({
            'content': '<html>PROFILE EXISTS</html>',
            'code': '200',
            'headers': {'content-type': 'text/html'},
        })
        site = {
            'name': 'Fingerprint Example',
            'cat': 'social',
            'uri_check': 'https://example.com/{account}',
            'e_code': 200,
            'm_code': 404,
            'e_string': 'PROFILE EXISTS',
            'm_string': 'NOT FOUND',
        }

        module.checkSite('alice', site)

        self.assertTrue(any(module.siteResults.values()))

    def test_bytes_response_is_decoded_before_fingerprint_matching(self):
        module = self._module_for_site_check({
            'content': b'PROFILE EXISTS',
            'code': '200',
            'headers': {'content-type': 'text/plain'},
        })
        site = {
            'name': 'Bytes Example',
            'cat': 'social',
            'uri_check': 'https://example.com/{account}',
            'e_code': 200,
            'm_code': 404,
            'e_string': 'PROFILE EXISTS',
            'm_string': 'NOT FOUND',
        }

        module.checkSite('alice', site)

        self.assertTrue(any(module.siteResults.values()))

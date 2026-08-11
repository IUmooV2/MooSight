import pytest
import unittest

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

import unittest
from unittest.mock import patch

from spiderfoot.modern_webui import ModernSpiderFootWebUi


class TestModernWebUi(unittest.TestCase):

    def test_startscan_route_is_exposed_to_cherrypy(self):
        self.assertTrue(getattr(ModernSpiderFootWebUi.startscan, 'exposed', False))

    @patch('spiderfoot.modern_webui.LegacySpiderFootWebUi.startscan')
    @patch('spiderfoot.modern_webui.SpiderFootHelpers.targetTypeFromString')
    def test_startscan_normalizes_unrecognized_bare_username(self, target_type, legacy_start):
        target_type.return_value = None
        ui = ModernSpiderFootWebUi.__new__(ModernSpiderFootWebUi)
        legacy_start.return_value = 'ok'

        result = ui.startscan('test', 'Nithsie', '', '', 'Footprint')

        self.assertEqual(result, 'ok')
        legacy_start.assert_called_once_with('test', '"Nithsie"', '', '', 'Footprint')

    @patch('spiderfoot.modern_webui.LegacySpiderFootWebUi.startscan')
    @patch('spiderfoot.modern_webui.SpiderFootHelpers.targetTypeFromString')
    def test_startscan_normalizes_instagram_profile_url_even_if_url_is_recognized(self, target_type, legacy_start):
        target_type.return_value = 'INTERNET_NAME'
        ui = ModernSpiderFootWebUi.__new__(ModernSpiderFootWebUi)
        legacy_start.return_value = 'ok'

        ui.startscan('test', 'https://www.instagram.com/sonrie.99/', '', '', 'Footprint')

        legacy_start.assert_called_once_with('test', '"sonrie.99"', '', '', 'Footprint')

    @patch('spiderfoot.modern_webui.LegacySpiderFootWebUi.startscan')
    @patch('spiderfoot.modern_webui.SpiderFootHelpers.targetTypeFromString')
    def test_startscan_preserves_recognized_domain(self, target_type, legacy_start):
        target_type.return_value = 'INTERNET_NAME'
        ui = ModernSpiderFootWebUi.__new__(ModernSpiderFootWebUi)
        legacy_start.return_value = 'ok'

        ui.startscan('test', 'example.com', '', '', 'Footprint')

        legacy_start.assert_called_once_with('test', 'example.com', '', '', 'Footprint')


if __name__ == '__main__':
    unittest.main()

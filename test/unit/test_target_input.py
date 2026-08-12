import unittest

from spiderfoot.target_input import normalize_scan_target


class TestTargetInput(unittest.TestCase):

    def test_preserves_existing_quoted_username(self):
        self.assertEqual(normalize_scan_target('"sonrie.99"'), '"sonrie.99"')

    def test_normalizes_at_username(self):
        self.assertEqual(normalize_scan_target('@sonrie.99', recognized_type=None), '"sonrie.99"')

    def test_normalizes_unrecognized_bare_username(self):
        self.assertEqual(normalize_scan_target('Nithsie', recognized_type=None), '"Nithsie"')

    def test_preserves_recognized_target(self):
        self.assertEqual(normalize_scan_target('example.com', recognized_type='INTERNET_NAME'), 'example.com')

    def test_normalizes_supported_profile_urls(self):
        cases = {
            'https://www.instagram.com/sonrie.99/': '"sonrie.99"',
            'https://x.com/sonrie99': '"sonrie99"',
            'https://www.tiktok.com/@sonrie.99': '"sonrie.99"',
            'https://www.reddit.com/user/sonrie99/': '"sonrie99"',
            'https://bsky.app/profile/sonrie.test': '"sonrie.test"',
            'https://account.venmo.com/u/sonrie99': '"sonrie99"',
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(normalize_scan_target(value, recognized_type='INTERNET_NAME'), expected)

    def test_does_not_convert_deep_github_url_to_username(self):
        value = 'https://github.com/openai/openai-python'
        self.assertEqual(normalize_scan_target(value, recognized_type='INTERNET_NAME'), value)

    def test_rejects_path_like_bare_input(self):
        self.assertEqual(normalize_scan_target('bad/name', recognized_type=None), 'bad/name')


if __name__ == '__main__':
    unittest.main()

import unittest

from spiderfoot.account_health import (
    dumps_health,
    loads_health,
    merge_health,
    normalize_health,
    reliability,
)


class TestAccountHealth(unittest.TestCase):

    def test_normalize_health_rejects_bad_shape_and_negative_counts(self):
        data = normalize_health({
            'Good': {'positive': '2', 'negative': 1, 'ambiguous': -3, 'error': 'bad'},
            'Broken': 'not-a-record',
            '': {'positive': 1},
        })
        self.assertEqual(data['Good']['positive'], 2)
        self.assertEqual(data['Good']['negative'], 1)
        self.assertEqual(data['Good']['ambiguous'], 0)
        self.assertEqual(data['Good']['error'], 0)
        self.assertNotIn('Broken', data)
        self.assertNotIn('', data)

    def test_merge_health_accumulates_without_usernames(self):
        merged = merge_health(
            {'Instagram': {'positive': 3, 'negative': 5, 'ambiguous': 1, 'error': 0}},
            {'Instagram': {'positive': 1, 'negative': 2, 'ambiguous': 0, 'error': 1,
                           'last_detail': 'HTTP 429'}},
        )
        self.assertEqual(merged['Instagram']['positive'], 4)
        self.assertEqual(merged['Instagram']['negative'], 7)
        self.assertEqual(merged['Instagram']['error'], 1)
        self.assertEqual(merged['Instagram']['last_detail'], 'HTTP 429')

    def test_reliability_is_new_with_few_observations(self):
        label, score, total = reliability({'positive': 2, 'negative': 1})
        self.assertEqual(label, 'NEW')
        self.assertEqual(total, 3)
        self.assertGreater(score, 0.5)

    def test_reliability_healthy_when_responses_are_consistent(self):
        label, score, total = reliability({
            'positive': 10, 'negative': 30, 'ambiguous': 1, 'error': 1})
        self.assertEqual(label, 'HEALTHY')
        self.assertEqual(total, 42)
        self.assertGreaterEqual(score, 0.85)

    def test_reliability_mixed_and_unstable(self):
        mixed, _, _ = reliability({'positive': 4, 'negative': 4, 'ambiguous': 3, 'error': 1})
        unstable, _, _ = reliability({'positive': 1, 'negative': 2, 'ambiguous': 5, 'error': 5})
        self.assertEqual(mixed, 'MIXED')
        self.assertEqual(unstable, 'UNSTABLE')

    def test_serialization_is_deterministic_and_corruption_safe(self):
        payload = dumps_health({
            'B': {'positive': 1},
            'A': {'negative': 2},
        })
        self.assertLess(payload.index('"A"'), payload.index('"B"'))
        self.assertEqual(loads_health(payload)['A']['negative'], 2)
        self.assertEqual(loads_health('{broken'), {})
        self.assertEqual(loads_health(b'\xff'), {})


if __name__ == '__main__':
    unittest.main()

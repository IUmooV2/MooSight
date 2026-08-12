import unittest

from spiderfoot.network import NetworkResult, NetworkState
from spiderfoot.network_legacy import empty_legacy_result, network_result_to_legacy, to_legacy_result


class TestLegacyNetworkAdapter(unittest.TestCase):

    def test_success_preserves_legacy_shape_and_string_status_code(self):
        result = NetworkResult(
            state=NetworkState.SUCCESS,
            status_code=200,
            url="https://example.com/",
            content=b"hello",
            headers={"content-type": "text/plain"},
        )

        legacy = network_result_to_legacy(result)

        self.assertEqual(legacy["code"], "200")
        self.assertIsNone(legacy["status"])
        self.assertEqual(legacy["content"], "hello")
        self.assertEqual(legacy["headers"]["content-type"], "text/plain")
        self.assertEqual(legacy["realurl"], "https://example.com/")

    def test_not_found_is_not_reported_as_transport_error(self):
        result = NetworkResult(
            state=NetworkState.NOT_FOUND,
            status_code=404,
            url="https://example.com/missing",
            content=b"not found",
        )
        legacy = network_result_to_legacy(result)
        self.assertEqual(legacy["code"], "404")
        self.assertIsNone(legacy["status"])

    def test_timeout_remains_indeterminate_instead_of_becoming_not_found(self):
        result = NetworkResult(
            state=NetworkState.TIMEOUT,
            url="https://example.com/",
            error="request timed out",
        )
        legacy = network_result_to_legacy(result)
        self.assertIsNone(legacy["code"])
        self.assertEqual(legacy["status"], "request timed out")
        self.assertIsNone(legacy["content"])

    def test_binary_content_can_be_preserved(self):
        binary = b"\xff\xfe\x00\x01"
        result = NetworkResult(
            state=NetworkState.SUCCESS,
            status_code=200,
            url="https://example.com/file",
            content=binary,
        )
        legacy = network_result_to_legacy(result, decode_content=False)
        self.assertEqual(legacy["content"], binary)

    def test_undecodable_bytes_remain_bytes_when_decoding_requested(self):
        binary = b"\xff\xfe\xfd"
        result = NetworkResult(
            state=NetworkState.SUCCESS,
            status_code=200,
            url="https://example.com/file",
            content=binary,
        )
        legacy = network_result_to_legacy(result)
        self.assertEqual(legacy["content"], binary)

    def test_to_legacy_result_preserves_requested_url_when_result_has_none(self):
        result = NetworkResult(state=NetworkState.NETWORK_ERROR, url=None)
        legacy = to_legacy_result(result, requested_url="https://example.com/")
        self.assertEqual(legacy["realurl"], "https://example.com/")

    def test_to_legacy_result_honors_disable_content_encoding(self):
        binary = b"hello"
        result = NetworkResult(
            state=NetworkState.SUCCESS,
            status_code=200,
            url="https://example.com/file",
            content=binary,
        )
        legacy = to_legacy_result(result, disable_content_encoding=True)
        self.assertEqual(legacy["content"], binary)

    def test_empty_result_is_fresh_each_time(self):
        first = empty_legacy_result("https://one.example/")
        second = empty_legacy_result("https://two.example/")
        first["headers"] = {"x": "1"}

        self.assertEqual(first["realurl"], "https://one.example/")
        self.assertEqual(second["realurl"], "https://two.example/")
        self.assertIsNone(second["headers"])

    def test_wrong_type_is_rejected(self):
        with self.assertRaises(TypeError):
            network_result_to_legacy({})


if __name__ == "__main__":
    unittest.main()

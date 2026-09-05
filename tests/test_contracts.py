import unittest

from rock_arch_broker.contracts import sanitize_text


class ContractSanitizationTests(unittest.TestCase):
    def test_display_text_removes_json_surrogates_before_utf8_boundaries(self):
        value = sanitize_text("safe\ud800text\udfff", 40)

        self.assertEqual(value, "safetext")
        self.assertEqual(value.encode("utf-8"), b"safetext")


if __name__ == "__main__":
    unittest.main()

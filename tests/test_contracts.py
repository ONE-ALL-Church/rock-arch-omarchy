import unittest

from rock_arch_broker.contracts import parse_search_query, sanitize_text


class ContractSanitizationTests(unittest.TestCase):
    def test_defined_type_aliases_parse_to_the_same_scope(self):
        for prefix in ("dt", "definedtype", "definedtypes", "DT"):
            self.assertEqual(parse_search_query(prefix + ": Connection"), ("Connection", "Defined Types"))

    def test_display_text_removes_json_surrogates_before_utf8_boundaries(self):
        value = sanitize_text("safe\ud800text\udfff", 40)

        self.assertEqual(value, "safetext")
        self.assertEqual(value.encode("utf-8"), b"safetext")


if __name__ == "__main__":
    unittest.main()

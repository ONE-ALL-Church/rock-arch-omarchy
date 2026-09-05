import unittest

from rock_arch_broker.http_security import (
    HttpSecurityError,
    RejectRedirects,
    decode_bounded_json,
    validate_rock_cookie_header,
)


class HttpSecurityTests(unittest.TestCase):
    def test_validated_cookie_is_returned_unchanged(self):
        self.assertEqual(
            validate_rock_cookie_header(".ROCK=private-session"),
            ".ROCK=private-session",
        )

    def test_cookie_validation_rejects_header_injection_and_attributes(self):
        for value in (None, "other=value", ".ROCK=value; Path=/", ".ROCK=a\nb"):
            with self.subTest(value=value), self.assertRaises(HttpSecurityError):
                validate_rock_cookie_header(value)

    def test_json_decoder_normalizes_invalid_and_deep_input(self):
        for raw in (b"not-json", b"[" * 100_000 + b"]" * 100_000):
            with self.subTest(size=len(raw)), self.assertRaises(HttpSecurityError):
                decode_bounded_json(raw)

    def test_redirect_handler_refuses_every_redirect(self):
        handler = RejectRedirects()
        self.assertIsNone(
            handler.redirect_request(None, None, 302, "Found", {}, "https://other")
        )


if __name__ == "__main__":
    unittest.main()

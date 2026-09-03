import json
import unittest
from email.message import Message
from unittest.mock import patch

from rock_lens_broker.origin import DEFAULT_ROCK_ORIGIN
from rock_lens_broker.rock_session import (
    RockSessionError,
    RockSessionHttpClient,
    RockSessionProvider,
)
from rock_lens_broker.secret_store import SecretToolStore


class FakeSecretStore:
    def __init__(self):
        self.values = {}
        self.fail_clear = False

    def available(self):
        return True

    def lookup(self, context, kind):
        return self.values.get((context, kind))

    def store(self, context, kind, value):
        self.values[(context, kind)] = value

    def clear(self, context, kind):
        if self.fail_clear:
            return False
        self.values.pop((context, kind), None)
        return True


class FakeLoginClient:
    def __init__(self, cookie=".ROCK=test-session"):
        self.cookie = cookie
        self.calls = []
        self.failure = None

    def login(self, origin, username, password):
        self.calls.append((origin, username, password))
        if self.failure:
            raise self.failure
        return self.cookie


class FakeResponse:
    def __init__(self, cookies):
        self.status = 204
        self.headers = Message()
        for cookie in cookies:
            self.headers.add_header("Set-Cookie", cookie)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def getcode(self):
        return self.status


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        return self.response


class RockSessionTests(unittest.TestCase):
    def setUp(self):
        self.profile_id = "a" * 32
        self.secrets = FakeSecretStore()
        self.login = FakeLoginClient()
        self.session = RockSessionProvider(
            DEFAULT_ROCK_ORIGIN,
            self.profile_id,
            secret_store=self.secrets,
            http=self.login,
        )

    def test_configure_verifies_then_saves_credentials_and_cookie_privately(self):
        self.session.configure("rock-user", "private-password")
        self.assertEqual(
            self.login.calls,
            [(DEFAULT_ROCK_ORIGIN, "rock-user", "private-password")],
        )
        self.assertTrue(self.session.status()["configured"])
        self.assertEqual(self.session.status()["state"], "connected")
        serialized = json.dumps(self.session.status()).lower()
        for private in ("rock-user", "private-password", ".rock", "cookie"):
            self.assertNotIn(private, serialized)

    def test_failed_new_login_does_not_replace_working_saved_login(self):
        self.session.configure("old-user", "old-password")
        self.login.failure = RockSessionError("rock_login_failed")
        with self.assertRaisesRegex(RockSessionError, "login_failed"):
            self.session.configure("new-user", "new-password")
        self.assertIn("old-user", self.secrets.values.values())
        self.assertIn("old-password", self.secrets.values.values())
        self.assertNotIn("new-user", self.secrets.values.values())

    def test_legacy_cleanup_failure_restores_working_saved_login(self):
        self.session.configure("old-user", "old-password")
        self.secrets.fail_clear = True

        with self.assertRaisesRegex(RockSessionError, "secure_storage_failed"):
            self.session.configure("new-user", "new-password")

        self.assertEqual(self.session._credentials(), ("old-user", "old-password"))

    def test_cookie_is_reused_in_memory_and_invalidation_logs_in_again(self):
        self.session.configure("rock-user", "private-password")
        with self.session.authenticated_cookie() as first:
            self.assertEqual(first, ".ROCK=test-session")
        with self.session.authenticated_cookie() as second:
            self.assertEqual(second, ".ROCK=test-session")
        self.assertEqual(len(self.login.calls), 1)
        self.session.invalidate_authenticated_cookie()
        with self.session.authenticated_cookie():
            pass
        self.assertEqual(len(self.login.calls), 2)

    def test_credentials_are_profile_scoped_and_sign_out_is_independent(self):
        self.session.configure("first-user", "first-password")
        self.session.set_profile("b" * 32, DEFAULT_ROCK_ORIGIN)
        self.assertFalse(self.session.status()["configured"])
        self.session.configure("second-user", "second-password")
        self.session.sign_out()
        self.assertFalse(self.session.status()["configured"])
        self.session.set_profile(self.profile_id, DEFAULT_ROCK_ORIGIN)
        self.assertTrue(self.session.status()["configured"])

    def test_old_magnus_secret_names_migrate_once(self):
        self.secrets.store(
            self.session.context,
            f"magnus_username:profile:{self.profile_id}",
            "legacy-user",
        )
        self.secrets.store(
            self.session.context,
            f"magnus_password:profile:{self.profile_id}",
            "legacy-password",
        )
        self.assertTrue(self.session.migrate_legacy_credentials())
        self.assertTrue(self.session.status()["configured"])
        self.assertFalse(
            any("magnus_" in key[1] for key in self.secrets.values)
        )

    def test_legacy_cleanup_failure_is_not_reported_as_migrated(self):
        self.secrets.store(
            self.session.context,
            self.session._secret_kind("rock_username"),
            "rock-user",
        )
        self.secrets.store(
            self.session.context,
            self.session._secret_kind("rock_password"),
            "private-password",
        )
        self.secrets.fail_clear = True

        with self.assertRaisesRegex(RockSessionError, "secure_storage_failed"):
            self.session.migrate_legacy_credentials()

    def test_http_login_posts_json_and_selects_only_the_rock_cookie(self):
        response = FakeResponse(
            ["Other=ignored; Path=/", ".ROCK=server-session; Path=/; Secure; HttpOnly"]
        )
        opener = FakeOpener(response)
        client = RockSessionHttpClient(opener)
        cookie = client.login(DEFAULT_ROCK_ORIGIN, "user", "password")
        self.assertEqual(cookie, ".ROCK=server-session")
        request, _ = opener.calls[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.full_url, DEFAULT_ROCK_ORIGIN + "/api/Auth/Login")
        self.assertEqual(
            json.loads(request.data), {"username": "user", "password": "password"}
        )

    def test_invalid_credentials_and_cookie_fail_closed(self):
        for username, password in (("", "password"), ("user", "bad\npassword")):
            with self.subTest(username=username), self.assertRaises(RockSessionError):
                self.session.configure(username, password)
        client = RockSessionHttpClient(FakeOpener(FakeResponse(["Other=value"])))
        with self.assertRaisesRegex(RockSessionError, "invalid_rock_cookie"):
            client.login(DEFAULT_ROCK_ORIGIN, "user", "password")

        attribute_like = RockSessionHttpClient(
            FakeOpener(FakeResponse(["Other=value; .ROCK=not-a-cookie-pair"]))
        )
        with self.assertRaisesRegex(RockSessionError, "invalid_rock_cookie"):
            attribute_like.login(DEFAULT_ROCK_ORIGIN, "user", "password")

    def test_sign_out_fails_closed_when_keyring_deletion_fails(self):
        self.session.configure("rock-user", "private-password")
        self.secrets.fail_clear = True

        with self.assertRaisesRegex(RockSessionError, "secure_storage_failed"):
            self.session.sign_out()

        self.assertEqual(self.session.status()["state"], "ready")
        self.assertTrue(self.session.status()["configured"])

    def test_secret_tool_reports_clear_failure(self):
        store = SecretToolStore("/usr/bin/secret-tool")
        with patch("subprocess.run") as run:
            run.return_value.returncode = 1
            self.assertFalse(store.clear(self.session.context, "rock_password"))


if __name__ == "__main__":
    unittest.main()

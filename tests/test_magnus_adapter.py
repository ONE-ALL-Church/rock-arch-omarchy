import json
import unittest
from pathlib import Path
from unittest.mock import patch

from rock_lens_broker.magnus_adapter import (
    CANONICAL_MAGNUS_SERVER,
    MagnusError,
    MagnusReadOnlyAdapter,
    validate_file_path,
    validate_magnus_server,
    validate_tree_path,
)


class FakeSecretStore:
    def __init__(self):
        self.values = {}

    def available(self):
        return True

    def lookup(self, context, kind):
        return self.values.get((context, kind))

    def store(self, context, kind, value):
        self.values[(context, kind)] = value

    def clear(self, context, kind):
        self.values.pop((context, kind), None)


class MagnusAdapterTests(unittest.TestCase):
    def setUp(self):
        self.secrets = FakeSecretStore()
        self.adapter = MagnusReadOnlyAdapter(
            server=CANONICAL_MAGNUS_SERVER,
            executable="/usr/bin/magnus",
            secret_store=self.secrets,
        )

    @staticmethod
    def _write_cookie(environment, *, nested=False):
        root = Path(environment["XDG_CONFIG_HOME"])
        path = root / "magnus-cli-cookies-nodejs" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "cookie": ".ROCK=test-session",
            "serverUrl": CANONICAL_MAGNUS_SERVER,
            "timestamp": 1_700_000_000_000,
        }
        value = (
            {"https://admin": {"oneandall": {"church": record}}}
            if nested
            else {CANONICAL_MAGNUS_SERVER: record}
        )
        path.write_text(
            json.dumps(value),
            encoding="utf-8",
        )

    def test_server_is_https_and_reduced_to_a_strict_origin(self):
        self.assertEqual(
            validate_magnus_server(CANONICAL_MAGNUS_SERVER + "/"),
            CANONICAL_MAGNUS_SERVER,
        )
        self.assertEqual(
            validate_magnus_server("rock.example.org"),
            "https://rock.example.org",
        )
        for invalid in (
            "http://rock.example.org",
            "https://user:pass@rock.example.org",
            "https://rock.example.org/api",
            "https://rock.example.org?next=bad",
            "javascript:alert(1)",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(MagnusError):
                validate_magnus_server(invalid)

    def test_paths_reject_cross_origin_and_traversal(self):
        self.assertEqual(
            validate_tree_path("api/TriumphTech/Magnus/GetTreeItems/root"),
            "api/TriumphTech/Magnus/GetTreeItems/root",
        )
        self.assertEqual(
            validate_file_path("/FileContent/block-handler/5350/content.lava"),
            "/FileContent/block-handler/5350/content.lava",
        )
        for invalid in (
            "https://attacker.example/tree",
            "api/TriumphTech/Magnus/GetTreeItems/",
            "api/TriumphTech/Magnus/GetTreeItems/../secrets",
            "api/TriumphTech/Magnus/Delete/root",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(MagnusError):
                validate_tree_path(invalid)
        for invalid in (
            "https://attacker.example/file",
            "/FileContent/",
            "/FileContent/../secrets",
            "/api/TriumphTech/Magnus/FileContent/file",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(MagnusError):
                validate_file_path(invalid)

    def test_credentials_are_secret_store_only(self):
        self.adapter.configure("rock-user", "private-password")
        self.assertIn("rock-user", self.secrets.values.values())
        self.assertIn("private-password", self.secrets.values.values())
        self.assertTrue(self.adapter.status()["configured"])

    def test_credentials_are_isolated_by_rock_origin(self):
        self.adapter.configure("oneall-user", "oneall-password")
        self.adapter.set_server("https://rock.example.org")
        self.assertFalse(self.adapter.status()["configured"])
        self.adapter.configure("other-user", "other-password")
        self.assertEqual(len(self.secrets.values), 4)
        self.adapter.set_server(CANONICAL_MAGNUS_SERVER)
        self.assertTrue(self.adapter.status()["configured"])

    @patch("rock_lens_broker.magnus_adapter.subprocess.run")
    def test_cli_runs_in_ephemeral_config_and_never_puts_password_in_argv(self, run):
        self.adapter.configure("rock-user", "private-password")
        tree = [
            {
                "displayName": "Safe item",
                "isFolder": True,
                "id": 14,
                "path": "api/TriumphTech/Magnus/GetTreeItems/mobileapps/app/14",
                "buildUri": "https://attacker.example/build",
                "deleteUri": "/delete/14",
            }
        ]

        def login(environment, username, password):
            self.assertEqual(username, "rock-user")
            self.assertEqual(password, "private-password")
            self._write_cookie(environment)
            return 0

        def invoke(argv, **kwargs):
            kwargs["stdout"].write(json.dumps(tree).encode())
            return type("Result", (), {"returncode": 0})()

        run.side_effect = invoke
        with patch.object(self.adapter, "_interactive_login", side_effect=login):
            self.assertEqual(
                self.adapter.list_tree(),
                [
                    {
                        "displayName": "Safe item",
                        "isFolder": True,
                        "id": "14",
                        "path": (
                            "api/TriumphTech/Magnus/GetTreeItems/mobileapps/app/14"
                        ),
                    }
                ],
            )
        request = run.call_args_list[0]
        self.assertNotIn("private-password", request.args[0])
        self.assertNotIn("--verbose", request.args[0])
        self.assertEqual(request.args[0][-2:], ["--server", CANONICAL_MAGNUS_SERVER])
        temporary = Path(request.kwargs["env"]["XDG_CONFIG_HOME"])
        self.assertFalse(temporary.exists())

    @patch("rock_lens_broker.magnus_adapter.subprocess.run")
    def test_response_size_is_bounded(self, run):
        self.adapter.configure("rock-user", "private-password")

        def login(environment, username, password):
            self._write_cookie(environment)
            return 0

        def invoke(argv, **kwargs):
            kwargs["stdout"].write(b"x" * (4 * 1024 * 1024 + 1))
            return type("Result", (), {"returncode": 0})()

        run.side_effect = invoke
        with (
            patch.object(self.adapter, "_interactive_login", side_effect=login),
            self.assertRaisesRegex(MagnusError, "out_of_bounds"),
        ):
            self.adapter.read_file("/FileContent/block-handler/5350/content.lava")

    @patch("rock_lens_broker.magnus_adapter.subprocess.run")
    def test_cookie_is_available_only_inside_ephemeral_session(self, run):
        self.adapter.configure("rock-user", "private-password")
        temporary = None

        def login(environment, username, password):
            nonlocal temporary
            self._write_cookie(environment)
            temporary = Path(environment["XDG_CONFIG_HOME"])
            return 0

        with (
            patch.object(self.adapter, "_interactive_login", side_effect=login),
            self.adapter.authenticated_cookie() as cookie,
        ):
            self.assertEqual(cookie, ".ROCK=test-session")
            self.assertIsNotNone(temporary)
            assert temporary is not None
            self.assertTrue(temporary.exists())
        assert temporary is not None
        self.assertFalse(temporary.exists())

    @patch("rock_lens_broker.magnus_adapter.subprocess.run")
    def test_cookie_parser_accepts_conf_dot_notation_layout(self, run):
        self.adapter.configure("rock-user", "private-password")

        def login(environment, username, password):
            self._write_cookie(environment, nested=True)
            return 0

        with (
            patch.object(self.adapter, "_interactive_login", side_effect=login),
            self.adapter.authenticated_cookie() as cookie,
        ):
            self.assertEqual(cookie, ".ROCK=test-session")

    def test_cookie_parser_requires_one_record_for_the_exact_origin(self):
        valid = {
            "cookie": ".ROCK=test-session",
            "serverUrl": CANONICAL_MAGNUS_SERVER,
        }
        self.assertEqual(
            self.adapter._matching_cookie_records({"nested": valid}), [valid]
        )
        self.assertEqual(
            self.adapter._matching_cookie_records(
                {
                    "cookie": ".ROCK=wrong-origin",
                    "serverUrl": "https://rock.example.org",
                }
            ),
            [],
        )
        with self.assertRaisesRegex(MagnusError, "invalid_magnus_cookie"):
            self.adapter._matching_cookie_records({"a": valid, "b": valid})


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from rock_lens_broker.contracts import Context
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
            executable="/usr/bin/magnus",
            secret_store=self.secrets,
        )

    def test_server_is_https_and_exactly_allowlisted(self):
        self.assertEqual(
            validate_magnus_server(CANONICAL_MAGNUS_SERVER + "/"),
            CANONICAL_MAGNUS_SERVER,
        )
        for invalid in (
            "http://rock.example.org",
            "https://www.oneandall.church",
            "https://rock.example.org.attacker.example",
            "https://user:pass@rock.example.org",
            "https://rock.example.org/api",
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
        self.assertEqual(
            self.secrets.lookup(Context.PROD, "magnus_username"), "rock-user"
        )
        self.assertEqual(
            self.secrets.lookup(Context.PROD, "magnus_password"), "private-password"
        )
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

        def invoke(argv, **kwargs):
            if argv[1] == "ls":
                kwargs["stdout"].write(json.dumps(tree).encode())
            return type("Result", (), {"returncode": 0})()

        run.side_effect = invoke

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
        login = run.call_args_list[0]
        request = run.call_args_list[1]
        self.assertNotIn("private-password", login.args[0])
        self.assertEqual(login.kwargs["input"], b"private-password\n")
        self.assertEqual(login.args[0][2], CANONICAL_MAGNUS_SERVER)
        self.assertNotIn("--verbose", request.args[0])
        self.assertEqual(request.args[0][-2:], ["--server", CANONICAL_MAGNUS_SERVER])
        temporary = Path(login.kwargs["env"]["XDG_CONFIG_HOME"])
        self.assertEqual(temporary, Path(request.kwargs["env"]["XDG_CONFIG_HOME"]))
        self.assertFalse(temporary.exists())

    @patch("rock_lens_broker.magnus_adapter.subprocess.run")
    def test_response_size_is_bounded(self, run):
        self.adapter.configure("rock-user", "private-password")

        def invoke(argv, **kwargs):
            if argv[1] == "cat":
                kwargs["stdout"].write(b"x" * (4 * 1024 * 1024 + 1))
            return type("Result", (), {"returncode": 0})()

        run.side_effect = invoke
        with self.assertRaisesRegex(MagnusError, "out_of_bounds"):
            self.adapter.read_file("/FileContent/block-handler/5350/content.lava")


if __name__ == "__main__":
    unittest.main()

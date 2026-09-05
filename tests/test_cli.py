import getpass
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from rock_arch_broker.cli import (
    BrokerClient,
    CliError,
    _parser,
    _request,
    run,
)
from rock_arch_broker.terminal_access import CLI_CLIENT


class FakeClient:
    def __init__(self, status=None):
        self.calls = []
        self.status = status or {
            "ok": True,
            "profiles": {"activeProfileId": "", "profiles": []},
        }

    def request(self, payload):
        self.calls.append(payload)
        if payload["op"] == "status":
            return self.status
        return {"ok": True, "echo": payload}


class FakeConnection:
    def __init__(self, response):
        self.response = bytearray(response)
        self.sent = b""
        self.closed = False

    def sendall(self, content):
        self.sent += content

    def recv(self, size):
        if not self.response:
            return b""
        content = bytes(self.response[:size])
        del self.response[:size]
        return content

    def close(self):
        self.closed = True


class RockArchCliTests(unittest.TestCase):
    @patch("rock_arch_broker.cli._omarchy_shell")
    def test_settings_values_and_atomic_json_batch_use_the_broker(self, refresh):
        client = FakeClient()
        _request(_parser().parse_args(["settings", "set", "recentLinks", "false"]), client)
        with patch("sys.stdin", io.StringIO('{"tabOrder":["knowledge","search","personal","magnus"],"showPersonContext":false}')):
            _request(_parser().parse_args(["settings", "set", "--stdin"]), client)
        self.assertEqual(client.calls[0], {"op": "settings_update", "settings": {"recentLinks": False}})
        self.assertEqual(client.calls[1]["settings"]["tabOrder"], ["knowledge", "search", "personal", "magnus"])
        self.assertEqual(refresh.call_count, 2)

    def test_settings_schema_is_offline_and_invalid_input_never_reaches_broker(self):
        client = FakeClient()
        schema = _request(_parser().parse_args(["settings", "schema"]), client)["schema"]
        self.assertIn("tabOrder", schema["fields"])
        self.assertNotIn("onboardingSetupCompleted", schema["fields"])
        for raw in ("not json", "[]", "{}", '{"unknown":true}', "[" * 20000, "\udcff"):
            with self.subTest(raw=raw[:40]), patch("sys.stdin", io.StringIO(raw)), self.assertRaises(CliError):
                _request(_parser().parse_args(["settings", "set", "--stdin"]), client)
        self.assertEqual(client.calls, [])

    @patch("rock_arch_broker.cli._omarchy_shell")
    def test_shortcut_set_rechecks_revision_and_requires_confirmation(self, refresh):
        class ShortcutClient(FakeClient):
            def request(self, payload):
                self.calls.append(payload)
                return {"ok": True, "shortcut": {"state": "available", "editable": True, "revision": "current-revision"}}

        client = ShortcutClient()
        with self.assertRaisesRegex(CliError, "confirmation_required"):
            _request(_parser().parse_args(["shortcuts", "set", "Super+R"]), client)
        self.assertEqual(client.calls, [])
        _request(_parser().parse_args(["shortcuts", "set", "Super+R", "--confirm"]), client)
        self.assertEqual(client.calls[-1], {"op": "shortcut_install", "combo": "Super+R", "revision": "current-revision", "confirmed": True})
        refresh.assert_called_once_with("preferences")

    def test_search_and_knowledge_commands_map_to_broker_operations(self):
        client = FakeClient()

        search = _parser().parse_args(["search", "123", "--entity", "groups"])
        _request(search, client)
        knowledge = _parser().parse_args(["knowledge", "search", "mm: Group"])
        _request(knowledge, client)
        detail = _parser().parse_args(["knowledge", "get", "opaque-result"])
        _request(detail, client)
        file_hash = _parser().parse_args(["magnus", "hash", "opaque-file"])
        _request(file_hash, client)

        self.assertEqual(
            client.calls,
            [
                {"op": "search", "query": "g: 123"},
                {"op": "knowledge_search", "query": "mm: Group"},
                {"op": "knowledge_result", "safeId": "opaque-result"},
                {"op": "magnus_hash", "safeId": "opaque-file"},
            ],
        )

    def test_stdin_credentials_are_private_and_do_not_prompt(self):
        credentials = {"name": "Demo", "domain": "demo.example.org", "username": "fixture", "password": "synthetic-password"}
        output = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps(credentials))),
            patch("getpass.getpass") as password_prompt,
            patch.object(BrokerClient, "request", return_value={"ok": True}) as request,
            redirect_stdout(output),
        ):
            self.assertEqual(run(["profiles", "add", "--stdin"]), 0)
        request.assert_called_once_with({"op": "profile_add", **credentials})
        password_prompt.assert_not_called()
        self.assertNotIn("synthetic-password", output.getvalue())
        for raw in ('{"password":"secret"}', '{"username":"u","password":"p","unknown":true}', "x" * 9000,
                    "\udcff", '{"username":"u","password":"\\ud800"}'):
            client = FakeClient()
            with patch("sys.stdin", io.StringIO(raw)), self.assertRaises(CliError):
                _request(_parser().parse_args(["login", "--stdin"]), client)
            self.assertEqual(client.calls, [])

    def test_login_is_interactive_and_password_has_no_argument(self):
        parser = _parser()
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["login", "--password", "secret"])
        args = parser.parse_args(["login"])
        client = FakeClient()

        with (
            patch(
                "builtins.input",
                side_effect=["Production", "rock.example.org", "agent-user"],
            ),
            patch.object(getpass, "getpass", return_value="private-password"),
        ):
            _request(args, client)

        self.assertEqual(client.calls[0], {"op": "status"})
        self.assertEqual(
            client.calls[1],
            {
                "op": "rock_configure",
                "name": "Production",
                "domain": "rock.example.org",
                "username": "agent-user",
                "password": "private-password",
            },
        )

    def test_login_updates_the_active_profile(self):
        profile_id = "a" * 32
        client = FakeClient(
            {
                "ok": True,
                "profiles": {
                    "activeProfileId": profile_id,
                    "profiles": [
                        {"id": profile_id, "name": "Production", "isActive": True}
                    ],
                },
            }
        )

        with (
            patch("builtins.input", return_value="agent-user"),
            patch.object(getpass, "getpass", return_value="private-password"),
        ):
            _request(_parser().parse_args(["login"]), client)

        self.assertEqual(
            client.calls[-1],
            {
                "op": "profile_credentials_update",
                "username": "agent-user",
                "password": "private-password",
            },
        )

    def test_external_and_destructive_actions_require_confirmation(self):
        client = FakeClient()
        cases = [
            ["open", "opaque-result"],
            ["knowledge", "open", "opaque-result"],
            ["links", "clear"],
            ["links", "activate", "opaque-result"],
            ["profiles", "sign-out"],
            ["profiles", "remove", "a" * 32],
            ["magnus", "download", "opaque-file"],
            ["magnus", "copy", "opaque-file", "hash"],
            ["magnus", "open", "opaque-file"],
            ["magnus", "build", "opaque-app"],
            ["updates", "install"],
        ]

        for argv in cases:
            with (
                self.subTest(argv=argv),
                self.assertRaisesRegex(CliError, "confirmation_required"),
            ):
                _request(_parser().parse_args(argv), client)
        self.assertEqual(client.calls, [])

        _request(
            _parser().parse_args(["magnus", "build", "opaque-app", "--confirm"]),
            client,
        )
        self.assertEqual(
            client.calls[-1],
            {
                "op": "magnus_build",
                "safeId": "opaque-app",
                "confirmed": True,
            },
        )

    def test_private_query_input_and_interactive_fallback(self):
        client = FakeClient()
        with patch("sys.stdin", io.StringIO("Ada Rivera\n")):
            _request(_parser().parse_args(["search", "--stdin"]), client)
        with patch("sys.stdin", io.StringIO("mm: Group\n")):
            _request(_parser().parse_args(["knowledge", "search"]), client)

        self.assertEqual(
            client.calls,
            [
                {"op": "search", "query": "Ada Rivera"},
                {"op": "knowledge_search", "query": "mm: Group"},
            ],
        )
        with self.assertRaisesRegex(CliError, "query_input_conflict"):
            _request(
                _parser().parse_args(["search", "visible", "--stdin"]), client
            )

    def test_schema_is_offline_and_every_emitted_object_is_versioned(self):
        output = io.StringIO()
        with redirect_stdout(output):
            result = run(["schema"])
        payload = json.loads(output.getvalue())

        self.assertEqual(result, 0)
        self.assertEqual(payload["protocolVersion"], 1)
        self.assertEqual(payload["schema"]["protocolVersion"], 1)
        self.assertFalse(payload["schema"]["buildStatus"]["completionVerifiable"])

    def test_dry_run_uses_description_without_confirmation(self):
        client = FakeClient()
        _request(
            _parser().parse_args(
                ["magnus", "build", "opaque-app", "--dry-run"]
            ),
            client,
        )
        clear = _request(
            _parser().parse_args(["links", "clear", "--dry-run"]), client
        )

        self.assertEqual(
            client.calls[-1],
            {"op": "action_preview", "safeId": "opaque-app", "action": "build"},
        )
        self.assertFalse(clear["dryRun"]["executed"])

    def test_ui_handoff_sends_query_only_through_the_broker(self):
        client = FakeClient()
        with (
            patch("sys.stdin", io.StringIO("private person name\n")),
            patch("rock_arch_broker.cli._omarchy_shell") as shell,
        ):
            response = _request(
                _parser().parse_args(["ui", "open", "search", "--stdin"]),
                client,
            )

        self.assertEqual(
            client.calls,
            [
                {
                    "op": "ui_handoff_set",
                    "view": "search",
                    "query": "private person name",
                }
            ],
        )
        shell.assert_called_once_with("handoff")
        self.assertEqual(response["ui"], {"state": "opened", "view": "search"})

    def test_build_receipt_commands_map_to_broker(self):
        client = FakeClient()
        _request(_parser().parse_args(["magnus", "builds"]), client)
        _request(
            _parser().parse_args(["magnus", "build-status", "build-abc"]),
            client,
        )
        self.assertEqual(
            client.calls,
            [
                {"op": "magnus_builds"},
                {"op": "magnus_build_status", "buildId": "build-abc"},
            ],
        )

    def test_client_adds_the_official_marker_and_reads_one_bounded_response(self):
        connection = FakeConnection(b'{"ok":true,"value":"safe"}\nignored')
        client = BrokerClient(Path("/unused"))
        with patch.object(client, "_connect", return_value=connection):
            response = client.request({"op": "status"})

        sent = json.loads(connection.sent)
        self.assertEqual(sent, {"op": "status", "client": CLI_CLIENT})
        self.assertEqual(response["value"], "safe")
        self.assertTrue(connection.closed)

    def test_client_refuses_a_non_socket_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o700)
            path = root / "broker.sock"
            path.write_text("not a socket", encoding="utf-8")
            path.chmod(0o600)

            with self.assertRaisesRegex(CliError, "unsafe_broker_socket"):
                BrokerClient(path, auto_start=False).request({"op": "status"})

    def test_client_refuses_a_relative_socket_path(self):
        with self.assertRaisesRegex(CliError, "unsafe_broker_socket"):
            BrokerClient(Path("broker.sock"), auto_start=False).request(
                {"op": "status"}
            )


if __name__ == "__main__":
    unittest.main()

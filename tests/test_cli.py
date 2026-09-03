import getpass
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from rock_lens_broker.cli import (
    BrokerClient,
    CliError,
    _parser,
    _request,
)
from rock_lens_broker.terminal_access import CLI_CLIENT


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

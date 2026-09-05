import asyncio
import http.client
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from rock_arch_broker.cli import BrokerClient, CliError
from rock_arch_broker.http_security import (
    HttpSecurityError,
    decode_bounded_json,
    validate_rock_cookie_header,
)
from rock_arch_broker.magnus_adapter import (
    MagnusError,
    MagnusReadOnlyAdapter,
    MagnusTarget,
)
from rock_arch_broker.navigation import NavigationError, validate_rock_url
from rock_arch_broker.rock_rest_adapter import RockRestError, RockRestHttpClient
from rock_arch_broker.server import BrokerServer
from rock_arch_broker.updates import UpdateManager


class SecurityRegressionTests(unittest.TestCase):
    def test_exhausted_download_names_never_delete_an_existing_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for index in range(1000):
                name = "file.txt" if index == 0 else f"file ({index}).txt"
                (directory / name).write_bytes(b"existing")
            adapter = MagnusReadOnlyAdapter(Mock(), downloads_dir=directory)
            safe_id = adapter._register(MagnusTarget("file", "/FileContent/file.txt", "file.txt"))
            with patch.object(adapter, "read_file", return_value=b"new"), self.assertRaisesRegex(
                MagnusError, "magnus_download_failed"
            ):
                adapter.download(safe_id)
            self.assertEqual(len(list(directory.iterdir())), 1000)
            self.assertTrue(all(path.read_bytes() == b"existing" for path in directory.iterdir()))

    def test_failed_download_cleans_up_only_the_file_it_created(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "file.txt").write_bytes(b"existing")
            adapter = MagnusReadOnlyAdapter(Mock(), downloads_dir=directory)
            safe_id = adapter._register(MagnusTarget("file", "/FileContent/file.txt", "file.txt"))
            with patch.object(adapter, "read_file", return_value=b"new"), patch(
                "rock_arch_broker.magnus_adapter.os.fsync", side_effect=OSError("disk full")
            ), self.assertRaisesRegex(MagnusError, "magnus_download_failed"):
                adapter.download(safe_id)
            self.assertEqual([path.name for path in directory.iterdir()], ["file.txt"])
            self.assertEqual((directory / "file.txt").read_bytes(), b"existing")

    def test_nonfinite_and_overlong_json_numbers_are_stable_errors(self):
        for raw in (b"9" * 5000, b"NaN", b"Infinity", b"-Infinity", b"1e999"):
            with self.subTest(size=len(raw)), self.assertRaises(HttpSecurityError):
                decode_bounded_json(raw)

    def test_cookie_rejects_non_ascii_and_del_before_http_encoding(self):
        for value in (".ROCK=\u2603", ".ROCK=\x7f", ".ROCK=\u00e9"):
            with self.subTest(value=value), self.assertRaises(HttpSecurityError):
                validate_rock_cookie_header(value)

    def test_update_check_encoding_failure_finishes_with_a_stable_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            manager = UpdateManager(Path(temporary) / "updates.json", plugin_root=Path(temporary))
            manager._state["state"] = "checking"
            with patch.object(manager, "_check_once", side_effect=UnicodeError("private output")):
                manager._check_worker()
            self.assertEqual(manager._state["state"], "error")
            self.assertEqual(manager._state["error"], "update_check_failed")

    def test_cli_rejects_malformed_json_numbers_without_a_traceback(self):
        for raw in (b'{"value":' + b"9" * 5000 + b"}\n", b'{"value":NaN}\n'):
            connection = Mock()
            connection.recv.side_effect = [raw, b""]
            with self.subTest(size=len(raw)), self.assertRaisesRegex(CliError, "invalid_broker_response"):
                BrokerClient(Path("/unused"))._read_response(connection)

    def test_malformed_navigation_authorities_use_stable_errors(self):
        for url in ("https://rock.example.org:bad/path", "https://[broken/path"):
            with self.subTest(url=url), self.assertRaises(NavigationError):
                validate_rock_url(url, "https://rock.example.org")
        self.assertEqual(validate_rock_url("/page/1", "https://[::1]"), "https://[::1]/page/1")

    def test_http_protocol_failures_return_stable_errors(self):
        opener = Mock()
        opener.open.side_effect = http.client.BadStatusLine("private server response")
        with self.assertRaisesRegex(RockRestError, "rock_request_failed"):
            RockRestHttpClient(opener=opener).get_json("/api/People", {}, ".ROCK=fixture")

    def test_completed_update_check_uses_current_consent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            launched = []
            manager = UpdateManager(root / "updates.json", plugin_root=root,
                                    process_launcher=lambda *args: launched.append(args))
            manager._managed = True
            # A background check must only discover an update. A later status
            # request supplies the current saved preference before installation.
            checked = {**manager._state, "state": "available", "updateAvailable": True,
                       "lastCheckedAt": "2099-01-01T00:00:00Z"}
            with patch.object(manager, "_check_once", return_value=checked):
                manager._check_worker()
            self.assertEqual(manager.status(automatic_install=False)["state"], "available")
            self.assertEqual(launched, [])
            with patch.object(manager, "start_update", return_value={"state": "updating"}) as start:
                self.assertEqual(manager.status(automatic_install=True)["state"], "updating")
                start.assert_called_once()


class BrokerInputRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_bad_numeric_request_does_not_break_the_connection(self):
        with tempfile.TemporaryDirectory() as temporary, patch("rock_arch_broker.server.Broker"):
            server = BrokerServer(Path(temporary) / "socket", Path(temporary) / "state")
        server.broker.handle.return_value = {"ok": True}
        reader = asyncio.StreamReader()
        reader.feed_data(b'{"number":' + b"9" * 5000 + b'}\n{"op":"status"}\n')
        reader.feed_eof()
        writer = Mock(drain=AsyncMock(), wait_closed=AsyncMock())
        await server._client(reader, writer)
        responses = [json.loads(call.args[0]) for call in writer.write.call_args_list]
        self.assertEqual(responses, [{"ok": False, "error": "invalid_json"}, {"ok": True}])
        server.broker.handle.assert_called_once_with({"op": "status"})

import asyncio
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rock_arch_broker.server import BrokerServer


class BrokerServerSecurityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        with patch("rock_arch_broker.server.Broker"):
            self.server = BrokerServer(root / "broker.sock", root / "state.json")

    async def test_regular_file_at_socket_path_is_never_deleted(self):
        self.server.socket_path.write_text("keep me", encoding="utf-8")
        self.server.socket_path.chmod(0o600)

        with self.assertRaisesRegex(RuntimeError, "unsafe_socket_path"):
            await self.server._claim_socket_path()

        self.assertEqual(
            self.server.socket_path.read_text(encoding="utf-8"), "keep me"
        )

    async def test_insecure_stale_socket_is_refused(self):
        stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        stale.bind(str(self.server.socket_path))
        stale.close()
        self.server.socket_path.chmod(0o666)

        with self.assertRaisesRegex(RuntimeError, "unsafe_socket_path"):
            await self.server._claim_socket_path()

        self.assertTrue(self.server.socket_path.exists())

    async def test_private_stale_socket_can_be_reclaimed(self):
        stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        stale.bind(str(self.server.socket_path))
        stale.close()
        self.server.socket_path.chmod(0o600)

        self.assertTrue(await self.server._claim_socket_path())
        self.assertFalse(self.server.socket_path.exists())

    async def test_active_private_socket_causes_second_broker_to_exit(self):
        async def accept(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            writer.close()
            await writer.wait_closed()

        active = await asyncio.start_unix_server(
            accept, path=str(self.server.socket_path)
        )
        self.server.socket_path.chmod(0o600)
        self.addAsyncCleanup(active.wait_closed)
        self.addCleanup(active.close)

        self.assertFalse(await self.server._claim_socket_path())
        self.assertTrue(self.server.socket_path.exists())

    async def test_socket_directory_must_be_owned_by_current_user(self):
        parent = self.server.socket_path.parent
        self.assertTrue(parent.is_dir())
        with patch(
            "rock_arch_broker.server.os.getuid", return_value=os.getuid() + 1
        ), self.assertRaisesRegex(RuntimeError, "unsafe_socket_directory"):
            await self.server.run()

    async def test_stream_limit_failure_returns_a_stable_error(self):
        class FakeWriter:
            def __init__(self):
                self.output = bytearray()
                self.closed = False

            def write(self, value):
                self.output.extend(value)

            async def drain(self):
                return None

            def close(self):
                self.closed = True

            async def wait_closed(self):
                return None

        reader = asyncio.StreamReader(limit=16)
        reader.feed_data(b"x" * 64 + b"\n")
        reader.feed_eof()
        writer = FakeWriter()

        await self.server._client(reader, writer)

        self.assertEqual(
            bytes(writer.output), b'{"ok":false,"error":"request_too_large"}\n'
        )
        self.assertTrue(writer.closed)


if __name__ == "__main__":
    unittest.main()

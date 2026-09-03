from __future__ import annotations

import asyncio
import json
import os
import stat
from pathlib import Path

from .broker import Broker

MAX_REQUEST = 16 * 1024


class BrokerServer:
    def __init__(self, socket_path: Path, state_file: Path) -> None:
        self.socket_path = socket_path
        self.broker = Broker(state_file)

    async def _client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            while True:
                try:
                    line = await reader.readline()
                except (ValueError, asyncio.LimitOverrunError):
                    writer.write(b'{"ok":false,"error":"request_too_large"}\n')
                    await writer.drain()
                    break
                if not line:
                    break
                if len(line) > MAX_REQUEST:
                    response = {"ok": False, "error": "request_too_large"}
                else:
                    try:
                        request = json.loads(line)
                        response = (
                            self.broker.handle(request)
                            if isinstance(request, dict)
                            else {"ok": False, "error": "invalid_request"}
                        )
                    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError):
                        response = {"ok": False, "error": "invalid_json"}
                writer.write(
                    json.dumps(
                        response, separators=(",", ":"), ensure_ascii=True
                    ).encode()
                    + b"\n"
                )
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def run(self) -> None:
        os.umask(0o077)
        self.socket_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        parent_info = os.lstat(self.socket_path.parent)
        if (
            not stat.S_ISDIR(parent_info.st_mode)
            or parent_info.st_uid != os.getuid()
        ):
            raise RuntimeError("unsafe_socket_directory")
        self.socket_path.parent.chmod(0o700)
        if not await self._claim_socket_path():
            return
        server = await asyncio.start_unix_server(
            self._client, path=str(self.socket_path), limit=MAX_REQUEST + 1
        )
        self.socket_path.chmod(0o600)
        async with server:
            await server.serve_forever()

    async def _claim_socket_path(self) -> bool:
        """Return whether a new socket may be bound without deleting other files."""

        try:
            existing = os.lstat(self.socket_path)
        except FileNotFoundError:
            return True
        if (
            not stat.S_ISSOCK(existing.st_mode)
            or existing.st_uid != os.getuid()
            or existing.st_mode & 0o077
        ):
            raise RuntimeError("unsafe_socket_path")
        try:
            _, writer = await asyncio.open_unix_connection(str(self.socket_path))
        except OSError:
            try:
                current = os.lstat(self.socket_path)
            except FileNotFoundError:
                return True
            if (
                not stat.S_ISSOCK(current.st_mode)
                or current.st_uid != existing.st_uid
                or current.st_dev != existing.st_dev
                or current.st_ino != existing.st_ino
                or current.st_mode & 0o077
            ):
                raise RuntimeError("unsafe_socket_path")
            self.socket_path.unlink()
            return True
        writer.close()
        await writer.wait_closed()
        return False

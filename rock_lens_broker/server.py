from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from .broker import Broker

MAX_REQUEST = 16 * 1024


class BrokerServer:
    def __init__(self, socket_path: Path, state_file: Path) -> None:
        self.socket_path = socket_path
        self.broker = Broker(state_file)

    async def _client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while line := await reader.readline():
                if len(line) > MAX_REQUEST:
                    response = {"ok": False, "error": "request_too_large"}
                else:
                    try:
                        request = json.loads(line)
                        response = self.broker.handle(request) if isinstance(request, dict) else {"ok": False, "error": "invalid_request"}
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        response = {"ok": False, "error": "invalid_json"}
                writer.write(json.dumps(response, separators=(",", ":"), ensure_ascii=True).encode() + b"\n")
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def run(self) -> None:
        os.umask(0o077)
        self.socket_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.socket_path.parent.chmod(0o700)
        if self.socket_path.exists():
            try:
                reader, writer = await asyncio.open_unix_connection(str(self.socket_path))
                writer.close()
                await writer.wait_closed()
                return
            except OSError:
                self.socket_path.unlink(missing_ok=True)
        server = await asyncio.start_unix_server(self._client, path=str(self.socket_path))
        self.socket_path.chmod(0o600)
        async with server:
            await server.serve_forever()

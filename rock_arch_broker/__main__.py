from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from . import legacy_cli
from .server import BrokerServer
from .shortcuts import ShortcutManager
from .terminal_access import TerminalAccessManager


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in {"rock", "magnus"}:
        raise SystemExit(legacy_cli.run(sys.argv[1], sys.argv[2:]))
    runtime = (
        Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
        / "rock-arch"
    )
    state = (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "rock-arch"
    )
    parser = argparse.ArgumentParser(
        description="Owner-local Rock Arch broker"
    )
    parser.add_argument("--socket", type=Path, default=runtime / "broker.sock")
    parser.add_argument("--state-file", type=Path, default=state / "context")
    args = parser.parse_args()
    asyncio.run(
        BrokerServer(
            args.socket,
            args.state_file,
            terminal_access=TerminalAccessManager(),
            shortcuts=ShortcutManager(),
        ).run()
    )


if __name__ == "__main__":
    main()

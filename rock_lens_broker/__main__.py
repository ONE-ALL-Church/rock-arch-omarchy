from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from .server import BrokerServer


def main() -> None:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "rock-lens"
    state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "rock-lens"
    parser = argparse.ArgumentParser(description="Owner-local, read-only Rock Lens broker")
    parser.add_argument("--socket", type=Path, default=runtime / "broker.sock")
    parser.add_argument("--state-file", type=Path, default=state / "context")
    args = parser.parse_args()
    asyncio.run(BrokerServer(args.socket, args.state_file).run())


if __name__ == "__main__":
    main()

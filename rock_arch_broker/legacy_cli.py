"""Compatibility aliases; all supported commands use the broker client."""

from __future__ import annotations

import argparse
import sys

from . import cli


def run(group: str, argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog=f"python3 -m rock_arch_broker {group}",
        description="Deprecated aliases for rock-arch; use rock-arch --help.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("login" if group == "rock" else "configure")
    if group == "magnus":
        for name in ("ls", "cat", "hash"):
            diagnostic = commands.add_parser(name, help="retired raw-path diagnostic")
            diagnostic.add_argument("path", nargs="?")
            if name == "cat":
                diagnostic.add_argument("--output")
    args = parser.parse_args(argv)
    if args.command in {"ls", "cat", "hash"}:
        # Do not echo a potentially private server path or start the broker.
        parser.error(
            "raw-path diagnostics have been retired. Use 'rock-arch magnus browse' "
            "to obtain an opaque safeId, then 'rock-arch magnus preview SAFE_ID', "
            "'rock-arch magnus hash SAFE_ID', or "
            "'rock-arch magnus download SAFE_ID --confirm'."
        )
    target = (
        ["magnus", "status"] if group == "magnus" and args.command == "status"
        else ["status"] if args.command == "status"
        else ["login"]
    )
    print(f"Deprecated alias; use: rock-arch {' '.join(target)}", file=sys.stderr)
    return cli.run(target)

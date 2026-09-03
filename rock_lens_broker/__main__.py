from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import sys
from pathlib import Path

from .instance import InstanceStore, default_instance_path
from .magnus_adapter import (
    DEFAULT_TREE_PATH,
    MagnusError,
    MagnusReadOnlyAdapter,
)
from .origin import OriginError
from .profiles import ProfileError, ProfileStore
from .rock_session import RockSessionError, RockSessionProvider
from .server import BrokerServer


def magnus(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        description="Native Rock Magnus reads and controlled mobile app builds"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("configure")
    list_parser = commands.add_parser("ls")
    list_parser.add_argument("path", nargs="?", default=DEFAULT_TREE_PATH)
    cat_parser = commands.add_parser("cat")
    cat_parser.add_argument("path")
    cat_parser.add_argument("--output", type=Path)
    hash_parser = commands.add_parser("hash")
    hash_parser.add_argument("path")
    args = parser.parse_args(argv)
    instance_store = InstanceStore(default_instance_path())
    profile_store = ProfileStore(
        default_instance_path().with_name("profiles.json"), instance_store
    )
    active_profile = profile_store.active()
    session = RockSessionProvider(
        origin=active_profile.origin if active_profile else None,
        profile_id=active_profile.profile_id if active_profile else None,
    )
    adapter = MagnusReadOnlyAdapter(
        session, server=active_profile.origin if active_profile else None
    )
    try:
        session.migrate_legacy_credentials()
        if args.command == "status":
            if session.status()["configured"]:
                adapter.probe()
            print(
                json.dumps(
                    {"rock": session.status(), "magnus": adapter.status()},
                    sort_keys=True,
                )
            )
            return
        if args.command == "configure":
            try:
                default_domain = active_profile.origin if active_profile else ""
                suffix = f" [{default_domain}]" if default_domain else ""
                domain = input(
                    f"Rock domain (for example rock.example.org){suffix}: "
                ).strip() or default_domain
                if not active_profile or domain != active_profile.origin:
                    name = input("Profile name (blank uses the domain): ").strip()
                    active_profile = profile_store.add(name, domain)
                else:
                    active_profile = profile_store.set_active(
                        active_profile.profile_id
                    )
                session.set_profile(active_profile.profile_id, active_profile.origin)
                adapter.set_profile(active_profile.profile_id, active_profile.origin)
                username = input("Rock username: ")
                password = getpass.getpass("Rock password: ")
            except (EOFError, KeyboardInterrupt):
                raise SystemExit("\nRock login cancelled.") from None
            session.configure(username, password)
            has_magnus = adapter.probe()
            suffix = " Magnus access detected." if has_magnus else " Magnus access was not detected."
            print("Rock login saved in Secret Service." + suffix)
            return
        if args.command == "ls":
            print(json.dumps(adapter.list_tree(args.path), indent=2, sort_keys=True))
            return
        if args.command == "hash":
            print(adapter.hash_file(args.path))
            return
        content = adapter.read_file(args.path)
        if args.output:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(args.output, flags, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
            print(f"Saved {len(content)} bytes with owner-only permissions.")
        else:
            sys.stdout.buffer.write(content)
    except (MagnusError, RockSessionError, OriginError, ProfileError) as error:
        raise SystemExit(str(error)) from error


def rock(argv: list[str]) -> None:
    """User-facing aliases for the native Rock login shared by every feature."""

    parser = argparse.ArgumentParser(description="Native Rock profile login")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    commands.add_parser("login")
    args = parser.parse_args(argv)
    magnus(["configure" if args.command == "login" else "status"])


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "rock":
        rock(sys.argv[2:])
        return
    if len(sys.argv) > 1 and sys.argv[1] == "magnus":
        magnus(sys.argv[2:])
        return
    runtime = (
        Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
        / "rock-lens"
    )
    state = (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "rock-lens"
    )
    parser = argparse.ArgumentParser(
        description="Owner-local Rock Lens broker"
    )
    parser.add_argument("--socket", type=Path, default=runtime / "broker.sock")
    parser.add_argument("--state-file", type=Path, default=state / "context")
    args = parser.parse_args()
    asyncio.run(BrokerServer(args.socket, args.state_file).run())


if __name__ == "__main__":
    main()

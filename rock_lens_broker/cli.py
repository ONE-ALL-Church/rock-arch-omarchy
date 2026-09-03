from __future__ import annotations

import argparse
import getpass
import json
import os
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, NoReturn

from .terminal_access import CLI_CLIENT
from .version import VERSION

MAX_REQUEST_BYTES = 16 * 1024
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 120.0

ENTITY_PREFIXES = {
    "people": "p",
    "groups": "g",
    "group-types": "gt",
    "workflows": "w",
    "jobs": "j",
    "pages": "page",
    "content-types": "ct",
    "content-items": "c",
}


class CliError(Exception):
    def __init__(self, code: str, exit_code: int = 4) -> None:
        super().__init__(code)
        self.code = code
        self.exit_code = exit_code


def default_socket_path() -> Path:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    return runtime / "rock-arch/broker.sock"


class BrokerClient:
    """Bounded client for Rock Arch's owner-only local broker."""

    def __init__(
        self,
        socket_path: Path,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        auto_start: bool = True,
    ) -> None:
        self.socket_path = socket_path
        self.timeout = timeout
        self.auto_start = auto_start

    def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = dict(payload)
        request["client"] = CLI_CLIENT
        encoded = (
            json.dumps(request, separators=(",", ":"), ensure_ascii=True).encode(
                "ascii"
            )
            + b"\n"
        )
        if len(encoded) > MAX_REQUEST_BYTES:
            raise CliError("request_too_large", 2)
        connection = self._connect()
        try:
            connection.sendall(encoded)
            response = self._read_response(connection)
        finally:
            connection.close()
        if response.get("ok") is not True:
            code = str(response.get("error") or "request_failed")
            raise CliError(
                code,
                3 if code in {"broker_unavailable", "terminal_access_disabled"} else 4,
            )
        return response

    def _connect(self) -> socket.socket:
        if not self.socket_path.is_absolute():
            raise CliError("unsafe_broker_socket", 3)
        try:
            self._validate_socket()
            return self._open_socket()
        except FileNotFoundError:
            if not self.auto_start:
                raise CliError("broker_unavailable", 3) from None
        except (ConnectionRefusedError, TimeoutError):
            if not self.auto_start:
                raise CliError("broker_unavailable", 3) from None
        except OSError:
            raise CliError("unsafe_broker_socket", 3) from None

        self._start_broker()
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            try:
                self._validate_socket()
                return self._open_socket()
            except (FileNotFoundError, ConnectionRefusedError, TimeoutError):
                time.sleep(0.05)
            except OSError:
                raise CliError("unsafe_broker_socket", 3) from None
        raise CliError("broker_unavailable", 3)

    def _validate_socket(self) -> None:
        parent = self.socket_path.parent
        parent_info = os.lstat(parent)
        if (
            not stat.S_ISDIR(parent_info.st_mode)
            or parent_info.st_uid != os.getuid()
            or parent_info.st_mode & 0o077
        ):
            raise OSError("unsafe broker directory")
        info = os.lstat(self.socket_path)
        if (
            not stat.S_ISSOCK(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
        ):
            raise OSError("unsafe broker socket")

    def _open_socket(self) -> socket.socket:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(self.timeout)
        try:
            connection.connect(str(self.socket_path))
        except OSError:
            connection.close()
            raise
        return connection

    def _read_response(self, connection: socket.socket) -> dict[str, Any]:
        content = bytearray()
        while len(content) <= MAX_RESPONSE_BYTES:
            try:
                chunk = connection.recv(
                    min(64 * 1024, MAX_RESPONSE_BYTES + 1 - len(content))
                )
            except TimeoutError:
                raise CliError("broker_timeout", 3) from None
            if not chunk:
                break
            content.extend(chunk)
            newline = content.find(b"\n")
            if newline >= 0:
                del content[newline:]
                break
        if len(content) > MAX_RESPONSE_BYTES:
            raise CliError("response_too_large", 3)
        try:
            response = json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            raise CliError("invalid_broker_response", 3) from None
        if not isinstance(response, dict):
            raise CliError("invalid_broker_response", 3)
        return response

    def _start_broker(self) -> None:
        command = [
            sys.executable,
            "-m",
            "rock_lens_broker",
            "--socket",
            str(self.socket_path),
        ]
        try:
            # The executable and module are fixed; no shell or request data is used.
            subprocess.Popen(
                command,
                cwd=Path(__file__).resolve().parents[1],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                start_new_session=True,
            )
        except OSError:
            raise CliError("broker_unavailable", 3) from None


def _timeout(value: str) -> float:
    try:
        timeout = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("timeout must be a number") from None
    if not 1 <= timeout <= 300:
        raise argparse.ArgumentTypeError("timeout must be between 1 and 300 seconds")
    return timeout


def _confirmation(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="confirm this external or destructive action",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rock-arch",
        description="Owner-local CLI for Rock RMS, Rock Knowledge, and Magnus",
    )
    parser.add_argument("--version", action="version", version=f"Rock Arch {VERSION}")
    parser.add_argument("--socket", type=Path, default=default_socket_path())
    parser.add_argument(
        "--timeout",
        type=_timeout,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="broker timeout in seconds (1-300)",
    )
    parser.add_argument(
        "--no-start",
        action="store_true",
        help="do not start the owner-local broker when it is not running",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="indent JSON output for people; default output is compact JSON",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    status = commands.add_parser("status", help="show Rock Arch status")
    status.add_argument("--probe-magnus", action="store_true")

    capabilities = commands.add_parser(
        "capabilities", help="show searchable Rock entity types"
    )
    capabilities.add_argument("--refresh", action="store_true")
    commands.add_parser("login", help="interactively sign in the active profile")

    search = commands.add_parser("search", help="search enabled Rock entities")
    search.add_argument("query")
    search.add_argument("--entity", choices=sorted(ENTITY_PREFIXES))

    person = commands.add_parser("person", help="show bounded person context")
    person.add_argument("safe_id")

    knowledge = commands.add_parser("knowledge", help="search public Rock knowledge")
    knowledge_commands = knowledge.add_subparsers(
        dest="knowledge_command", required=True
    )
    knowledge_search = knowledge_commands.add_parser("search", help="search knowledge")
    knowledge_search.add_argument("query")
    knowledge_get = knowledge_commands.add_parser("get", help="read a result")
    knowledge_get.add_argument("safe_id")
    knowledge_open = knowledge_commands.add_parser("open", help="open a public source")
    knowledge_open.add_argument("safe_id")
    _confirmation(knowledge_open)

    links = commands.add_parser("links", help="list or activate Rock links")
    link_commands = links.add_subparsers(dest="links_command", required=True)
    link_commands.add_parser("personal", help="list Personal Links")
    link_commands.add_parser("recent", help="list Recent Links")
    link_clear = link_commands.add_parser("clear", help="clear local Recent Links")
    _confirmation(link_clear)
    link_activate = link_commands.add_parser(
        "activate", help="open or rerun a recent link"
    )
    link_activate.add_argument("safe_id")
    _confirmation(link_activate)

    open_item = commands.add_parser("open", help="open an opaque Rock result")
    open_item.add_argument("safe_id")
    _confirmation(open_item)

    profiles = commands.add_parser("profiles", help="manage local Rock profiles")
    profile_commands = profiles.add_subparsers(dest="profiles_command", required=True)
    profile_commands.add_parser("list", help="list profiles")
    profile_add = profile_commands.add_parser("add", help="interactively add a profile")
    profile_add.add_argument("--name")
    profile_add.add_argument("--domain")
    profile_add.add_argument("--username")
    profile_use = profile_commands.add_parser("use", help="switch active profile")
    profile_use.add_argument("profile_id")
    profile_commands.add_parser("test", help="test the active profile")
    profile_rename = profile_commands.add_parser("rename", help="rename a profile")
    profile_rename.add_argument("profile_id")
    profile_rename.add_argument("name")
    profile_sign_out = profile_commands.add_parser(
        "sign-out", help="clear the active profile login"
    )
    _confirmation(profile_sign_out)
    profile_remove = profile_commands.add_parser("remove", help="remove a profile")
    profile_remove.add_argument("profile_id")
    _confirmation(profile_remove)

    magnus = commands.add_parser("magnus", help="use controlled Magnus features")
    magnus_commands = magnus.add_subparsers(dest="magnus_command", required=True)
    magnus_commands.add_parser("status", help="probe Magnus access")
    magnus_browse = magnus_commands.add_parser("browse", help="browse a folder")
    magnus_browse.add_argument("safe_id", nargs="?", default="")
    magnus_help = {
        "preview": "read a bounded text preview",
        "hash": "calculate SHA-256 without returning file contents",
        "download": "save a file privately without overwrite",
        "open": "open the item in Rock",
        "build": "start a confirmed mobile-app build",
    }
    for name, help_text in magnus_help.items():
        child = magnus_commands.add_parser(name, help=help_text)
        child.add_argument("safe_id")
        if name in {"download", "open", "build"}:
            _confirmation(child)
    magnus_copy = magnus_commands.add_parser("copy", help="copy content or SHA-256")
    magnus_copy.add_argument("safe_id")
    magnus_copy.add_argument("value", choices=("content", "hash"))
    _confirmation(magnus_copy)

    updates = commands.add_parser("updates", help="check or install plugin updates")
    update_commands = updates.add_subparsers(dest="updates_command", required=True)
    update_commands.add_parser("status")
    update_commands.add_parser("check")
    update_install = update_commands.add_parser("install")
    _confirmation(update_install)
    return parser


def _require_confirmation(args: argparse.Namespace) -> None:
    if not getattr(args, "confirm", False):
        raise CliError("confirmation_required", 2)


def _request(args: argparse.Namespace, client: BrokerClient) -> dict[str, Any]:
    if args.command == "status":
        return client.request({"op": "status", "probeMagnus": args.probe_magnus})
    if args.command == "capabilities":
        return client.request({"op": "search_capabilities", "refresh": args.refresh})
    if args.command == "login":
        return _login(client)
    if args.command == "search":
        query = args.query
        if args.entity:
            query = f"{ENTITY_PREFIXES[args.entity]}: {query}"
        return client.request({"op": "search", "query": query})
    if args.command == "person":
        return client.request({"op": "person_quick_look", "safeId": args.safe_id})
    if args.command == "knowledge":
        return _knowledge_request(args, client)
    if args.command == "links":
        return _links_request(args, client)
    if args.command == "open":
        _require_confirmation(args)
        return client.request({"op": "open_navigation", "safeId": args.safe_id})
    if args.command == "profiles":
        return _profiles_request(args, client)
    if args.command == "magnus":
        return _magnus_request(args, client)
    if args.command == "updates":
        return _updates_request(args, client)
    raise CliError("unsupported_command", 2)


def _knowledge_request(
    args: argparse.Namespace, client: BrokerClient
) -> dict[str, Any]:
    if args.knowledge_command == "search":
        return client.request({"op": "knowledge_search", "query": args.query})
    if args.knowledge_command == "get":
        return client.request({"op": "knowledge_result", "safeId": args.safe_id})
    _require_confirmation(args)
    return client.request({"op": "knowledge_open_source", "safeId": args.safe_id})


def _links_request(args: argparse.Namespace, client: BrokerClient) -> dict[str, Any]:
    if args.links_command in {"personal", "recent"}:
        section = "personal" if args.links_command == "personal" else "quick_returns"
        return client.request({"op": "navigation_status", "section": section})
    _require_confirmation(args)
    if args.links_command == "clear":
        return client.request({"op": "recent_links_clear"})
    return client.request(
        {"op": "activate_recent", "safeId": args.safe_id, "confirmed": True}
    )


def _profiles_request(args: argparse.Namespace, client: BrokerClient) -> dict[str, Any]:
    if args.profiles_command == "list":
        return client.request({"op": "profiles_status"})
    if args.profiles_command == "add":
        return _add_profile(args, client)
    if args.profiles_command == "use":
        return client.request({"op": "profile_switch", "profileId": args.profile_id})
    if args.profiles_command == "test":
        return client.request({"op": "profile_test"})
    if args.profiles_command == "rename":
        return client.request(
            {
                "op": "profile_rename",
                "profileId": args.profile_id,
                "name": args.name,
            }
        )
    _require_confirmation(args)
    if args.profiles_command == "sign-out":
        return client.request({"op": "profile_sign_out"})
    return client.request({"op": "profile_remove", "profileId": args.profile_id})


def _magnus_request(args: argparse.Namespace, client: BrokerClient) -> dict[str, Any]:
    if args.magnus_command == "status":
        return client.request({"op": "magnus_status"})
    if args.magnus_command == "browse":
        return client.request({"op": "magnus_browse", "safeId": args.safe_id})
    if args.magnus_command == "preview":
        return client.request({"op": "magnus_preview", "safeId": args.safe_id})
    if args.magnus_command == "hash":
        return client.request({"op": "magnus_hash", "safeId": args.safe_id})
    _require_confirmation(args)
    if args.magnus_command == "download":
        payload: dict[str, Any] = {
            "op": "magnus_download",
            "safeId": args.safe_id,
        }
    elif args.magnus_command == "copy":
        payload = {
            "op": "magnus_copy",
            "safeId": args.safe_id,
            "value": args.value,
        }
    elif args.magnus_command == "open":
        payload = {"op": "magnus_open", "safeId": args.safe_id}
    else:
        payload = {
            "op": "magnus_build",
            "safeId": args.safe_id,
            "confirmed": True,
        }
    return client.request(payload)


def _updates_request(args: argparse.Namespace, client: BrokerClient) -> dict[str, Any]:
    if args.updates_command == "status":
        return client.request({"op": "update_status"})
    if args.updates_command == "check":
        return client.request({"op": "update_check"})
    _require_confirmation(args)
    return client.request({"op": "update_start"})


def _login(client: BrokerClient) -> dict[str, Any]:
    status = client.request({"op": "status"})
    profiles = status.get("profiles", {})
    active_id = str(profiles.get("activeProfileId") or "")
    active = next(
        (
            row
            for row in profiles.get("profiles", [])
            if isinstance(row, dict) and row.get("id") == active_id
        ),
        None,
    )
    if not active:
        name = input("Profile name: ").strip()
        domain = input("Rock domain: ").strip()
        username = input("Rock username: ")
        password = getpass.getpass("Rock password: ")
        return client.request(
            {
                "op": "rock_configure",
                "name": name,
                "domain": domain,
                "username": username,
                "password": password,
            }
        )
    username = input(f"Rock username for {active.get('name', 'active profile')}: ")
    password = getpass.getpass("Rock password: ")
    return client.request(
        {
            "op": "profile_credentials_update",
            "username": username,
            "password": password,
        }
    )


def _add_profile(args: argparse.Namespace, client: BrokerClient) -> dict[str, Any]:
    name = args.name or input("Profile name: ").strip()
    domain = args.domain or input("Rock domain: ").strip()
    username = args.username or input("Rock username: ")
    password = getpass.getpass("Rock password: ")
    return client.request(
        {
            "op": "profile_add",
            "name": name,
            "domain": domain,
            "username": username,
            "password": password,
        }
    )


def _emit(payload: dict[str, Any], *, pretty: bool, stream: Any) -> None:
    json.dump(
        payload,
        stream,
        ensure_ascii=True,
        sort_keys=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    )
    stream.write("\n")


def run(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    client = BrokerClient(
        args.socket,
        timeout=args.timeout,
        auto_start=not args.no_start,
    )
    try:
        response = _request(args, client)
    except (EOFError, KeyboardInterrupt):
        _emit(
            {"ok": False, "error": "cancelled"},
            pretty=args.pretty,
            stream=sys.stderr,
        )
        return 130
    except CliError as error:
        _emit(
            {"ok": False, "error": error.code},
            pretty=args.pretty,
            stream=sys.stderr,
        )
        return error.exit_code
    _emit(response, pretty=args.pretty, stream=sys.stdout)
    return 0


def main() -> NoReturn:
    raise SystemExit(run())


if __name__ == "__main__":
    main()

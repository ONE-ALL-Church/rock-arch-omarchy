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

from .agent_protocol import PROTOCOL_VERSION, protocol_schema, settings_schema
from .http_security import HttpSecurityError, decode_bounded_json
from .profiles import EDITABLE_PREFERENCES
from .terminal_access import CLI_CLIENT
from .version import VERSION

MAX_REQUEST_BYTES = 16 * 1024
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 120.0
MAX_QUERY_INPUT_BYTES = 8 * 1024
IPC_TARGET = "oneall.rock-arch"
OMARCHY_SHELL_PATHS = (
    Path("/usr/bin/omarchy-shell"),
    Path("/usr/share/omarchy/bin/omarchy-shell"),
)

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
            response = decode_bounded_json(content)
        except HttpSecurityError:
            raise CliError("invalid_broker_response", 3) from None
        if not isinstance(response, dict):
            raise CliError("invalid_broker_response", 3)
        return response

    def _start_broker(self) -> None:
        command = [
            sys.executable,
            "-m",
            "rock_arch_broker",
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="describe the action and its effects without executing it",
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
    doctor = commands.add_parser("doctor", help="run redacted diagnostics")
    doctor.add_argument("--refresh", action="store_true")
    commands.add_parser("schema", help="show the versioned agent contract")

    settings = commands.add_parser("settings", help="read and edit panel preferences as JSON")
    setting_commands = settings.add_subparsers(dest="settings_command", required=True)
    setting_commands.add_parser("get", help="read all editable preferences")
    setting_commands.add_parser("schema", help="describe preference types and allowed values")
    setting_set = setting_commands.add_parser("set", help="set one JSON value or an atomic object from stdin")
    setting_set.add_argument("key", nargs="?", choices=EDITABLE_PREFERENCES)
    setting_set.add_argument("value", nargs="?")
    setting_set.add_argument("--stdin", action="store_true")

    shortcuts = commands.add_parser("shortcuts", help="manage the optional global shortcut")
    shortcut_commands = shortcuts.add_subparsers(dest="shortcuts_command", required=True)
    shortcut_commands.add_parser("status")
    shortcut_check = shortcut_commands.add_parser("check", help="check a combination without changing it")
    shortcut_check.add_argument("combo")
    shortcut_set = shortcut_commands.add_parser("set", help="add or change a managed shortcut")
    shortcut_set.add_argument("combo")
    _confirmation(shortcut_set)
    shortcut_remove = shortcut_commands.add_parser("remove")
    _confirmation(shortcut_remove)

    capabilities = commands.add_parser(
        "capabilities", help="show searchable Rock entity types"
    )
    capabilities.add_argument("--refresh", action="store_true")
    login = commands.add_parser("login", help="sign in the active profile")
    login.add_argument("--stdin", action="store_true", help="read credentials privately as JSON from stdin")

    search = commands.add_parser("search", help="search enabled Rock entities")
    search.add_argument("query", nargs="?")
    search.add_argument(
        "--stdin", action="store_true", help="read the query privately from stdin"
    )
    search.add_argument("--entity", choices=sorted(ENTITY_PREFIXES))

    person = commands.add_parser("person", help="show bounded person context")
    person.add_argument("safe_id")

    knowledge = commands.add_parser("knowledge", help="search public Rock knowledge")
    knowledge_commands = knowledge.add_subparsers(
        dest="knowledge_command", required=True
    )
    knowledge_search = knowledge_commands.add_parser("search", help="search knowledge")
    knowledge_search.add_argument("query", nargs="?")
    knowledge_search.add_argument(
        "--stdin", action="store_true", help="read the query privately from stdin"
    )
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

    describe = commands.add_parser(
        "describe", help="describe an opaque ID without taking an action"
    )
    describe.add_argument("safe_id")

    profiles = commands.add_parser("profiles", help="manage local Rock profiles")
    profile_commands = profiles.add_subparsers(dest="profiles_command", required=True)
    profile_commands.add_parser("list", help="list profiles")
    profile_add = profile_commands.add_parser("add", help="interactively add a profile")
    profile_add.add_argument("--name")
    profile_add.add_argument("--domain")
    profile_add.add_argument("--username")
    profile_add.add_argument("--stdin", action="store_true", help="read profile and credentials privately as JSON from stdin")
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
    magnus_commands.add_parser("builds", help="list local build receipts")
    magnus_build_status = magnus_commands.add_parser(
        "build-status", help="show one local build receipt"
    )
    magnus_build_status.add_argument("build_id")
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

    ui = commands.add_parser("ui", help="handoff work to the Omarchy panel")
    ui_commands = ui.add_subparsers(dest="ui_command", required=True)
    ui_open = ui_commands.add_parser("open", help="open a Rock Arch panel view")
    ui_open.add_argument(
        "view",
        nargs="?",
        default="search",
        choices=("search", "links", "knowledge", "magnus", "settings"),
    )
    ui_open.add_argument("query", nargs="?")
    ui_open.add_argument(
        "--stdin", action="store_true", help="read a search query privately from stdin"
    )
    ui_commands.add_parser("close", help="close the Rock Arch panel")
    return parser


def _require_confirmation(args: argparse.Namespace) -> None:
    if not getattr(args, "confirm", False):
        raise CliError("confirmation_required", 2)


def _read_query(
    args: argparse.Namespace,
    *,
    prompt: str,
    interactive_when_missing: bool = True,
) -> str:
    query = getattr(args, "query", None)
    from_stdin = bool(getattr(args, "stdin", False) or query == "-")
    if query not in (None, "-") and getattr(args, "stdin", False):
        raise CliError("query_input_conflict", 2)
    if from_stdin or (query is None and not sys.stdin.isatty()):
        value = sys.stdin.read(MAX_QUERY_INPUT_BYTES + 1)
    elif query is None and interactive_when_missing:
        value = input(prompt)
    else:
        value = query or ""
    value = value.rstrip("\r\n")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        raise CliError("invalid_query_encoding", 2) from None
    if len(encoded) > MAX_QUERY_INPUT_BYTES:
        raise CliError("query_too_large", 2)
    return value


def _dry_run_safe(
    client: BrokerClient, safe_id: str, action: str
) -> dict[str, Any]:
    return client.request(
        {"op": "action_preview", "safeId": safe_id, "action": action}
    )


def _static_dry_run(action: str, side_effects: list[str]) -> dict[str, Any]:
    return {
        "ok": True,
        "dryRun": {
            "action": action,
            "confirmationRequired": True,
            "sideEffects": side_effects,
            "executed": False,
        },
    }


def _request(args: argparse.Namespace, client: BrokerClient) -> dict[str, Any]:
    if args.command == "status":
        return client.request({"op": "status", "probeMagnus": args.probe_magnus})
    if args.command == "doctor":
        response = client.request({"op": "doctor", "refresh": args.refresh})
        doctor = response.get("doctor")
        if isinstance(doctor, dict) and isinstance(doctor.get("checks"), list):
            doctor["checks"].insert(
                0,
                {"name": "broker_socket", "state": "healthy", "detail": "Connected"},
            )
        return response
    if args.command == "schema":
        return {"ok": True, "schema": protocol_schema()}
    if args.command == "settings":
        return _settings_request(args, client)
    if args.command == "shortcuts":
        return _shortcuts_request(args, client)
    if args.command == "capabilities":
        return client.request({"op": "search_capabilities", "refresh": args.refresh})
    if args.command == "login":
        return _login(client, _read_credentials() if args.stdin else None)
    if args.command == "search":
        query = _read_query(args, prompt="Search: ")
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
        if args.dry_run:
            return _dry_run_safe(client, args.safe_id, "open")
        _require_confirmation(args)
        return client.request({"op": "open_navigation", "safeId": args.safe_id})
    if args.command == "describe":
        return client.request({"op": "describe", "safeId": args.safe_id})
    if args.command == "profiles":
        return _profiles_request(args, client)
    if args.command == "magnus":
        return _magnus_request(args, client)
    if args.command == "updates":
        return _updates_request(args, client)
    if args.command == "ui":
        return _ui_request(args, client)
    raise CliError("unsupported_command", 2)


def _refresh_panel_preferences(response: dict[str, Any]) -> dict[str, Any]:
    try:
        _omarchy_shell("preferences")
        response["panelRefreshed"] = True
    except CliError:
        response["panelRefreshed"] = False
    return response


def _settings_request(args: argparse.Namespace, client: BrokerClient) -> dict[str, Any]:
    if args.settings_command == "schema":
        return {"ok": True, "schema": settings_schema()}
    if args.settings_command == "get":
        return client.request({"op": "settings_status"})
    if args.stdin:
        if args.key is not None or args.value is not None:
            raise CliError("settings_input_conflict", 2)
        try:
            raw = sys.stdin.read(MAX_REQUEST_BYTES + 1)
        except UnicodeError:
            raise CliError("invalid_settings_json", 2) from None
    else:
        if args.key is None or args.value is None:
            raise CliError("settings_input_required", 2)
        raw = args.value
    try:
        encoded = raw.encode("utf-8")
    except UnicodeError:
        raise CliError("invalid_settings_json", 2) from None
    if len(encoded) > MAX_REQUEST_BYTES:
        raise CliError("request_too_large", 2)
    try:
        value = json.loads(raw)
    except (ValueError, RecursionError):
        raise CliError("invalid_settings_json", 2) from None
    settings = value if args.stdin else {args.key: value}
    if not isinstance(settings, dict) or not settings or not set(settings).issubset(EDITABLE_PREFERENCES):
        raise CliError("invalid_preferences", 2)
    return _refresh_panel_preferences(client.request({"op": "settings_update", "settings": settings}))


def _shortcuts_request(args: argparse.Namespace, client: BrokerClient) -> dict[str, Any]:
    action = args.shortcuts_command
    combo = getattr(args, "combo", "")
    if action in {"status", "check"}:
        return client.request({"op": "shortcut_status", "combo": combo})
    if not args.dry_run:
        _require_confirmation(args)
    inspected = client.request({"op": "shortcut_status", "combo": combo})
    shortcut = inspected.get("shortcut", {})
    if shortcut.get("error"):
        raise CliError(str(shortcut["error"]))
    if action == "set" and shortcut.get("state") == "conflict":
        raise CliError("shortcut_conflict")
    if shortcut.get("editable") is not True:
        raise CliError("shortcut_unavailable")
    if not shortcut.get("managed") and (
        action == "remove" or (shortcut.get("currentCombo") and shortcut.get("state") != "configured")
    ):
        raise CliError("not_managed")
    if args.dry_run:
        preview = _static_dry_run(
            "setShortcut" if action == "set" else "removeShortcut",
            ["changes_managed_shortcut", "reloads_hyprland"] + (["restores_menu_icon"] if action == "remove" else []),
        )
        preview["shortcut"] = shortcut
        return preview
    response = client.request({
        "op": "shortcut_install" if action == "set" else "shortcut_remove",
        "combo": combo, "revision": shortcut.get("revision", ""), "confirmed": True,
    })
    if response.get("shortcut", {}).get("error"):
        raise CliError(str(response["shortcut"]["error"]))
    return _refresh_panel_preferences(response)


def _knowledge_request(
    args: argparse.Namespace, client: BrokerClient
) -> dict[str, Any]:
    if args.knowledge_command == "search":
        return client.request(
            {"op": "knowledge_search", "query": _read_query(args, prompt="Knowledge search: ")}
        )
    if args.knowledge_command == "get":
        return client.request({"op": "knowledge_result", "safeId": args.safe_id})
    if args.dry_run:
        return _dry_run_safe(client, args.safe_id, "knowledgeOpen")
    _require_confirmation(args)
    return client.request({"op": "knowledge_open_source", "safeId": args.safe_id})


def _links_request(args: argparse.Namespace, client: BrokerClient) -> dict[str, Any]:
    if args.links_command in {"personal", "recent"}:
        section = "personal" if args.links_command == "personal" else "quick_returns"
        return client.request({"op": "navigation_status", "section": section})
    if args.links_command == "clear":
        if args.dry_run:
            return _static_dry_run("clearRecentLinks", ["deletes_local_history"])
        _require_confirmation(args)
        return client.request({"op": "recent_links_clear"})
    if args.dry_run:
        return _dry_run_safe(client, args.safe_id, "activate")
    _require_confirmation(args)
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
    if args.profiles_command == "sign-out":
        if args.dry_run:
            return _static_dry_run(
                "signOut", ["deletes_saved_login", "clears_memory_cookie"]
            )
        _require_confirmation(args)
        return client.request({"op": "profile_sign_out"})
    if args.dry_run:
        return _static_dry_run(
            "removeProfile",
            ["deletes_profile", "deletes_saved_login", "deletes_local_history"],
        )
    _require_confirmation(args)
    return client.request({"op": "profile_remove", "profileId": args.profile_id})


def _magnus_request(args: argparse.Namespace, client: BrokerClient) -> dict[str, Any]:
    if args.magnus_command == "status":
        return client.request({"op": "magnus_status"})
    if args.magnus_command == "builds":
        return client.request({"op": "magnus_builds"})
    if args.magnus_command == "build-status":
        return client.request(
            {"op": "magnus_build_status", "buildId": args.build_id}
        )
    if args.magnus_command == "browse":
        return client.request({"op": "magnus_browse", "safeId": args.safe_id})
    if args.magnus_command == "preview":
        return client.request({"op": "magnus_preview", "safeId": args.safe_id})
    if args.magnus_command == "hash":
        return client.request({"op": "magnus_hash", "safeId": args.safe_id})
    if args.dry_run:
        if args.magnus_command == "copy":
            action = "copyHash" if args.value == "hash" else "copyContent"
        else:
            action = {
                "download": "download",
                "open": "open",
                "build": "build",
            }[args.magnus_command]
        return _dry_run_safe(client, args.safe_id, action)
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
    if args.dry_run:
        return _static_dry_run(
            "installUpdate", ["fast_forwards_plugin", "reloads_omarchy_shell"]
        )
    _require_confirmation(args)
    return client.request({"op": "update_start"})


def _omarchy_shell(method: str) -> None:
    executable = next((path for path in OMARCHY_SHELL_PATHS if path.is_file()), None)
    if executable is None:
        raise CliError("omarchy_shell_unavailable", 3)
    try:
        completed = subprocess.run(
            [str(executable), IPC_TARGET, method],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        raise CliError("omarchy_shell_unavailable", 3) from None
    if completed.returncode != 0:
        raise CliError("ui_handoff_failed", 4)


def _ui_request(args: argparse.Namespace, client: BrokerClient) -> dict[str, Any]:
    if args.ui_command == "close":
        _omarchy_shell("close")
        return {"ok": True, "ui": {"state": "closed"}}
    query = ""
    if args.query is not None or args.stdin:
        query = _read_query(
            args, prompt="", interactive_when_missing=False
        )
    response = client.request(
        {"op": "ui_handoff_set", "view": args.view, "query": query}
    )
    _omarchy_shell("handoff")
    response["ui"] = {"state": "opened", "view": args.view}
    return response


def _read_credentials() -> dict[str, str]:
    try:
        raw = sys.stdin.read(MAX_QUERY_INPUT_BYTES + 1)
        encoded = raw.encode("utf-8")
    except UnicodeError:
        raise CliError("invalid_credential_input", 2) from None
    if len(encoded) > MAX_QUERY_INPUT_BYTES:
        raise CliError("credential_input_too_large", 2)
    try:
        value = json.loads(raw)
    except (ValueError, RecursionError):
        raise CliError("invalid_credential_input", 2) from None
    if (
        not isinstance(value, dict)
        or not {"username", "password"}.issubset(value)
        or not set(value).issubset({"name", "domain", "username", "password"})
        or any(not isinstance(item, str) or not item for item in value.values())
    ):
        raise CliError("invalid_credential_input", 2)
    try:
        for item in value.values():
            item.encode("utf-8")
    except UnicodeError:
        raise CliError("invalid_credential_input", 2) from None
    return value


def _login(client: BrokerClient, credentials: dict[str, str] | None = None) -> dict[str, Any]:
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
        if credentials is not None and not {"name", "domain"}.issubset(credentials):
            raise CliError("profile_details_required", 2)
        name = credentials["name"] if credentials is not None else input("Profile name: ").strip()
        domain = credentials["domain"] if credentials is not None else input("Rock domain: ").strip()
        username = credentials["username"] if credentials is not None else input("Rock username: ")
        password = credentials["password"] if credentials is not None else getpass.getpass("Rock password: ")
        return client.request(
            {
                "op": "rock_configure",
                "name": name,
                "domain": domain,
                "username": username,
                "password": password,
            }
        )
    if credentials is not None and set(credentials) != {"username", "password"}:
        raise CliError("credential_input_conflict", 2)
    username = credentials["username"] if credentials is not None else input(f"Rock username for {active.get('name', 'active profile')}: ")
    password = credentials["password"] if credentials is not None else getpass.getpass("Rock password: ")
    return client.request(
        {
            "op": "profile_credentials_update",
            "username": username,
            "password": password,
        }
    )


def _add_profile(args: argparse.Namespace, client: BrokerClient) -> dict[str, Any]:
    if args.stdin:
        if args.name is not None or args.domain is not None or args.username is not None:
            raise CliError("credential_input_conflict", 2)
        credentials = _read_credentials()
        if not {"name", "domain"}.issubset(credentials):
            raise CliError("profile_details_required", 2)
        return client.request({"op": "profile_add", **credentials})
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
    payload = dict(payload)
    payload.setdefault("protocolVersion", PROTOCOL_VERSION)
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

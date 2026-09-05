"""Opt-in, conflict-aware management of one Omarchy Lua shortcut.

Only our exact marked block is editable. No Lua is evaluated here and no
user-supplied command is executed. Source checkouts can inspect, but cannot save.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import re
import stat
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .shortcut_keymap import KeymapError, keyboard_symbols

COMMAND = "omarchy-shell shell summon oneall.rock-arch '{}'"
DESCRIPTION = "Rock Arch (managed shortcut)"
BEGIN = "-- BEGIN Rock Arch shortcut (managed v1)"
END = "-- END Rock Arch shortcut (managed v1)"
MAX_BYTES = 1024 * 1024
MODIFIERS = {"SUPER": 64, "CTRL": 4, "ALT": 8, "SHIFT": 1}
KEY = re.compile(r"(?:[A-Z0-9]|F(?:[1-9]|1[0-2]))\Z")


class ShortcutError(Exception):
    pass


def normalize_combo(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 80:
        raise ShortcutError("invalid_shortcut")
    parts = [part.strip().upper() for part in value.split("+")]
    mods, key = parts[:-1], parts[-1]
    if (
        "SUPER" not in mods
        or len(mods) != len(set(mods))
        or any(mod not in MODIFIERS for mod in mods)
        or not KEY.fullmatch(key)
    ):
        raise ShortcutError("invalid_shortcut")
    return " + ".join([mod for mod in MODIFIERS if mod in mods] + [key])


def render_block(combo: str) -> str:
    return f'\n{BEGIN}\no.bind("{combo}", "{DESCRIPTION}", "{COMMAND}")\n{END}\n'


def parse_binds(output: str) -> list[dict[str, str]]:
    # hyprctl -j binds is invalid JSON on some Lua Hyprland releases.
    bindings: list[dict[str, str]] = []
    for line in output.splitlines():
        if re.fullmatch(r"bind[a-z]*", line):
            bindings.append({})
        elif line.startswith("\t") and ": " in line and bindings:
            name, value = line[1:].split(": ", 1)
            bindings[-1][name] = value
        elif line.strip():
            raise ShortcutError("bindings_unavailable")
    if not bindings:
        raise ShortcutError("bindings_unavailable")
    for binding in bindings:
        if (
            not {"modmask", "key", "keycode", "submap", "dispatcher", "arg", "catchall"}
            <= binding.keys()
            or not binding["modmask"].isdigit()
            or not binding["keycode"].isdigit()
            or binding["catchall"] not in {"true", "false"}
        ):
            raise ShortcutError("bindings_unavailable")
    return bindings


def physical_code(binding: dict[str, str]) -> int:
    key = binding["key"].split(" + ")[-1].lower()
    if key.startswith("code:"):
        if not key[5:].isdigit():
            raise ShortcutError("bindings_unavailable")
        return int(key[5:])
    return int(binding["keycode"])


def matching_binds(
    bindings: list[dict[str, str]],
    combo: str,
    symbols: dict[int, set[str]] | None = None,
) -> list[dict[str, str]]:
    parts = combo.split(" + ")
    mask = sum(MODIFIERS[mod] for mod in parts[:-1])
    return [
        binding
        for binding in bindings
        if int(binding["modmask"]) == mask
        and (
            binding["key"].split(" + ")[-1].upper() == parts[-1]
            or binding["catchall"] == "true"
            or (
                physical_code(binding) != 0
                and (symbols is None or parts[-1] in symbols[physical_code(binding)])
            )
        )
    ]


def run_hyprctl(command: str) -> str:
    try:
        arguments = {
            "binds": ["binds"],
            "reload": ["reload"],
            "configerrors": ["configerrors"],
            "devices": ["-j", "devices"],
            "kb_file": ["getoption", "input:kb_file"],
        }[command]
        result = subprocess.run(
            ["/usr/bin/hyprctl", *arguments],
            check=True,
            capture_output=True,
            timeout=4,
            text=True,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError) as error:
        raise ShortcutError("hyprland_unavailable") from error
    if len(result.stdout) > 2 * MAX_BYTES:
        raise ShortcutError("bindings_unavailable")
    return result.stdout


@dataclass(frozen=True)
class FileSnapshot:
    content: bytes
    info: os.stat_result = field(compare=False)
    identity: tuple[int, ...]


def file_identity(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
        info.st_mode,
        info.st_uid,
    )


def read_config(path: Path) -> FileSnapshot:
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o022
        or info.st_size > MAX_BYTES
    ):
        raise ShortcutError("unsafe_config")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as source:
        opened = os.fstat(source.fileno())
        content = source.read(MAX_BYTES + 1)
    if file_identity(opened) != file_identity(info) or len(content) > MAX_BYTES:
        raise ShortcutError("config_changed")
    return FileSnapshot(content, info, file_identity(info))


class ShortcutManager:
    def __init__(
        self,
        hypr_dir: Path | None = None,
        run: Callable[[str], str] = run_hyprctl,
        *,
        installed: bool | None = None,
    ) -> None:
        self.directory = hypr_dir or Path.home() / ".config/hypr"
        self.path = self.directory / "bindings.lua"
        self.main_path = self.directory / "hyprland.lua"
        self.run = run
        self.installed = (
            installed
            if installed is not None
            else (
                Path(__file__).resolve().parents[1]
                == (Path.home() / ".config/omarchy/plugins/oneall.rock-arch").resolve()
            )
        )

    def request(
        self,
        operation: str,
        *,
        combo: Any = "",
        revision: Any = "",
        confirmed: bool = False,
    ) -> dict[str, Any]:
        try:
            if operation == "shortcut_status":
                return self._inspect(combo)[0]
            if not confirmed:
                raise ShortcutError("confirmation_required")
            if not self.installed:
                raise ShortcutError("source_checkout")
            return self._change(operation, combo, revision)
        except (OSError, UnicodeError, ShortcutError) as error:
            code = (
                str(error) if isinstance(error, ShortcutError) else "config_unavailable"
            )
            try:
                status = self._inspect(combo)[0]
            except (OSError, UnicodeError, ShortcutError):
                status = {
                    "state": "unavailable",
                    "editable": False,
                    "managed": False,
                    "currentCombo": "",
                    "combo": "SUPER + R",
                }
            return {**status, "error": code}

    def _inspect(self, candidate: Any = "") -> tuple[dict[str, Any], FileSnapshot, str]:
        directory = self.directory.lstat()
        if (
            not stat.S_ISDIR(directory.st_mode)
            or directory.st_uid != os.getuid()
            or directory.st_mode & 0o022
        ):
            raise ShortcutError("unsafe_config")
        main = read_config(self.main_path).content.decode("utf-8")
        if not re.search(r"""(?m)^require\(["']hypr\.bindings["']\)\s*$""", main):
            raise ShortcutError("unsupported_config")
        snapshot = read_config(self.path)
        source = snapshot.content.decode("utf-8")
        managed_combo, block = self._managed(source)
        raw_binds = self.run("binds")
        bindings = parse_binds(raw_binds)
        codes = {physical_code(binding) for binding in bindings} - {0}
        symbols: dict[int, set[str]] = {}
        keyboard_state = ""
        if codes:
            keyboard_state = self.run("devices")
            if self.run("kb_file").split("\n", 1)[0].strip() not in {
                "str:",
                "str: [[EMPTY]]",
            }:
                raise ShortcutError("keymap_unavailable")
            try:
                symbols = keyboard_symbols(keyboard_state, codes)
            except KeymapError as error:
                raise ShortcutError("keymap_unavailable") from error
        errors = self.run("configerrors").strip()
        # Recognize only explicit, literal existing Rock Arch bindings. Never adopt.
        external: list[str] = []
        for match in re.finditer(
            r"""(?m)^o\.bind\("([^"\n]+)", "Rock Arch", "([^"\n]+)"\)\s*$""",
            source.replace(block, "") if block else source,
        ):
            if match[2] == COMMAND:
                try:
                    external.append(normalize_combo(match[1]))
                except ShortcutError:
                    pass
        current = managed_combo
        if not current:
            current = next(
                (
                    key
                    for key in external
                    if self._active(bindings, key, False, symbols)
                ),
                "",
            )
        combo = normalize_combo(candidate or current or "SUPER + R")
        matches = matching_binds(bindings, combo, symbols)
        configured = bool(
            current == combo and self._active(bindings, combo, bool(block), symbols)
        )
        return (
            {
                "state": "configured"
                if configured
                else "conflict"
                if matches
                else "available",
                "combo": combo,
                "currentCombo": current,
                "managed": bool(block),
                "currentActive": bool(
                    current and self._active(bindings, current, bool(block), symbols)
                ),
                "editable": self.installed and not errors,
                "conflict": "; ".join(
                    re.sub(r"[\x00-\x1f\x7f]", "", item.get("description", ""))[:100]
                    or "Another Hyprland binding"
                    for item in matches[:3]
                ),
                "revision": hashlib.sha256(
                    snapshot.content
                    + main.encode()
                    + raw_binds.encode()
                    + keyboard_state.encode()
                ).hexdigest(),
                "error": "config_errors"
                if errors
                else ""
                if self.installed
                else "source_checkout",
            },
            snapshot,
            block,
        )

    @staticmethod
    def _managed(source: str) -> tuple[str, str]:
        if BEGIN not in source and END not in source:
            return "", ""
        match = re.search(
            r"\n"
            + re.escape(BEGIN)
            + r'\no\.bind\("([^"\n]+)"[^\n]*\)\n'
            + re.escape(END)
            + r"\n",
            source,
        )
        if source.count(BEGIN) != 1 or source.count(END) != 1 or not match:
            raise ShortcutError("managed_block_changed")
        combo = normalize_combo(match[1])
        if match[0] != render_block(combo):
            raise ShortcutError("managed_block_changed")
        return combo, match[0]

    @staticmethod
    def _active(
        bindings: list[dict[str, str]],
        combo: str,
        managed: bool,
        symbols: dict[int, set[str]],
    ) -> bool:
        matches = matching_binds(bindings, combo, symbols)
        if len(matches) != 1:
            return False
        binding = matches[0]
        return (
            not binding["submap"]
            and binding["catchall"] == "false"
            and binding["keycode"] == "0"
            and binding.get("description") == (DESCRIPTION if managed else "Rock Arch")
            and (
                binding["dispatcher"] == "__lua"
                or (binding["dispatcher"] == "exec" and binding["arg"] == COMMAND)
            )
        )

    def _change(self, operation: str, candidate: Any, revision: Any) -> dict[str, Any]:
        if operation not in {"shortcut_install", "shortcut_remove"}:
            raise ShortcutError("unsupported_operation")
        # Serialize our own writers, without waiting behind an unrelated process.
        self._inspect(candidate)
        lock_path = self.directory / ".rock-arch-shortcut.lock"
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "rb") as lock:
            info = os.fstat(lock.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_mode & 0o077
            ):
                raise ShortcutError("unsafe_config")
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            status, before, block = self._inspect(candidate)
            if not status["editable"]:
                raise ShortcutError(status["error"] or "unsupported_config")
            if not revision or revision != status["revision"]:
                raise ShortcutError("config_changed")
            if operation == "shortcut_remove":
                if not block:
                    raise ShortcutError("not_managed")
                content = before.content.replace(block.encode(), b"", 1)
            else:
                if status["state"] == "configured":
                    return status
                if status["state"] == "conflict":
                    raise ShortcutError("shortcut_conflict")
                if status["currentCombo"] and not block:
                    raise ShortcutError("not_managed")
                content = (
                    before.content.replace(block.encode(), b"", 1)
                    if block
                    else before.content
                )
                content += render_block(status["combo"]).encode()
            # Retain an owner-only backup, including when a later edit blocks rollback.
            self._temporary(before.content, 0o600, ".rock-arch-shortcut-backup-")
            written = self._replace(content, before)
            try:
                self.run("reload")
                for _ in range(15):
                    time.sleep(0.1)
                    result, _, _ = self._inspect(status["combo"])
                    if result["error"]:
                        raise ShortcutError("reload_failed")
                    if (
                        operation == "shortcut_install"
                        and result["state"] == "configured"
                    ):
                        return {**result, "saved": True}
                    if operation == "shortcut_remove" and not any(
                        item.get("description") == DESCRIPTION
                        for item in parse_binds(self.run("binds"))
                    ):
                        return {**result, "saved": True}
                raise ShortcutError("reload_failed")
            except (OSError, UnicodeError, ShortcutError) as error:
                try:
                    self._replace(before.content, written)
                except (OSError, ShortcutError):
                    raise ShortcutError("rollback_conflict") from error
                try:
                    self.run("reload")
                    time.sleep(0.1)
                    if self.run("configerrors").strip():
                        raise ShortcutError("rollback_failed")
                except (OSError, ShortcutError):
                    raise ShortcutError("rollback_failed") from error
                raise ShortcutError("change_rolled_back") from error

    def _temporary(self, content: bytes, mode: int, prefix: str) -> Path:
        descriptor, name = tempfile.mkstemp(
            prefix=prefix, suffix=".lua", dir=self.directory
        )
        path = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as output:
                os.fchmod(output.fileno(), mode)
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            return path
        except OSError:
            path.unlink(missing_ok=True)
            raise

    def _replace(self, content: bytes, expected: FileSnapshot) -> FileSnapshot:
        temporary = self._temporary(
            content, stat.S_IMODE(expected.info.st_mode), ".rock-arch-shortcut-"
        )
        try:
            if read_config(self.path) != expected:
                raise ShortcutError("config_changed")
            os.replace(temporary, self.path)
            return read_config(self.path)
        finally:
            temporary.unlink(missing_ok=True)

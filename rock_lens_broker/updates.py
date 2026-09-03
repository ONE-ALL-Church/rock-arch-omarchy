from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import tempfile
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .version import VERSION

PLUGIN_ID = "oneall.rock-arch"
CHECK_INTERVAL = timedelta(days=1)
MAX_UPDATE_STATE_BYTES = 16 * 1024
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
GIT = Path("/usr/bin/git")
OMARCHY = Path("/usr/bin/omarchy")
PYTHON = Path("/usr/bin/python3")

CommandRunner = Callable[[list[str], int], subprocess.CompletedProcess[str]]
ProcessLauncher = Callable[[list[str], Path], None]
Clock = Callable[[], datetime]


class UpdateError(Exception):
    """A stable updater error that contains no command output or local paths."""


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_time(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _default_command_runner(
    command: list[str], timeout: int
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment.setdefault("GIT_SSH_COMMAND", "ssh -oBatchMode=yes")
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=environment,
    )


def _default_process_launcher(command: list[str], working_directory: Path) -> None:
    subprocess.Popen(
        command,
        cwd=working_directory,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        start_new_session=True,
    )


def default_update_state() -> dict[str, Any]:
    return {
        "state": "idle",
        "availableVersion": "",
        "currentRevision": "",
        "availableRevision": "",
        "lastCheckedAt": "",
        "lastUpdatedAt": "",
        "operationStartedAt": "",
        "updateAvailable": False,
        "error": "",
    }


def write_update_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".updates-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(state, output, separators=(",", ":"), ensure_ascii=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


class UpdateManager:
    """Checks a fixed Omarchy plugin checkout and delegates installs to Omarchy."""

    def __init__(
        self,
        state_file: Path,
        plugin_root: Path | None = None,
        installed_root: Path | None = None,
        command_runner: CommandRunner | None = None,
        process_launcher: ProcessLauncher | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.state_file = state_file
        self.plugin_root = (plugin_root or Path(__file__).resolve().parents[1]).resolve()
        self.installed_root = (
            installed_root
            or Path.home() / ".config/omarchy/plugins" / PLUGIN_ID
        ).resolve()
        self._run_command = command_runner or _default_command_runner
        self._launch_process = process_launcher or _default_process_launcher
        self._clock = clock or utc_now
        self._lock = threading.Lock()
        self._check_thread: threading.Thread | None = None
        self._managed = self._is_managed_install()
        self._state = self._load_state()

    def status(
        self, *, refresh: bool = False, automatic_install: bool = False
    ) -> dict[str, Any]:
        with self._lock:
            if self._state["state"] == "updating":
                self._state = self._load_state()
            state = dict(self._state)
            checking = self._check_thread is not None and self._check_thread.is_alive()

        if not self._managed:
            return self._public_status(state)

        if automatic_install and state["state"] == "available":
            return self.start_update()

        if (
            not checking
            and state["state"] not in {"checking", "updating"}
            and (refresh or self._check_is_stale(state))
        ):
            self._begin_check(automatic_install)

        with self._lock:
            return self._public_status(self._state)

    def start_update(self) -> dict[str, Any]:
        if not self._managed:
            raise UpdateError("update_managed_manually")

        with self._lock:
            if self._state["state"] == "updating":
                return self._public_status(self._state)
            if not self._state.get("updateAvailable"):
                raise UpdateError("no_update_available")

        clean = self._git("status", "--porcelain", "--untracked-files=no", timeout=5)
        if clean.returncode != 0 or clean.stdout.strip():
            self._set_error("local_changes_prevent_update", state="modified")
            raise UpdateError("local_changes_prevent_update")

        with self._lock:
            self._state.update(
                state="updating",
                operationStartedAt=iso_time(self._clock()),
                error="",
            )
            write_update_state(self.state_file, self._state)

        command = [
            str(PYTHON),
            "-m",
            "rock_lens_broker.update_worker",
            "--state-file",
            str(self.state_file),
            "--plugin-root",
            str(self.plugin_root),
            "--parent-pid",
            str(os.getpid()),
        ]
        try:
            self._launch_process(command, self.plugin_root)
        except OSError as error:
            self._set_error("update_launch_failed")
            raise UpdateError("update_launch_failed") from error
        with self._lock:
            return self._public_status(self._state)

    def _begin_check(self, automatic_install: bool) -> None:
        with self._lock:
            if self._check_thread is not None and self._check_thread.is_alive():
                return
            self._state.update(
                state="checking",
                operationStartedAt=iso_time(self._clock()),
                error="",
            )
            write_update_state(self.state_file, self._state)
            self._check_thread = threading.Thread(
                target=self._check_worker,
                args=(automatic_install,),
                name="rock-arch-update-check",
                daemon=True,
            )
            self._check_thread.start()

    def _check_worker(self, automatic_install: bool) -> None:
        try:
            checked = self._check_once()
        except (OSError, subprocess.SubprocessError, UpdateError):
            with self._lock:
                checked = dict(self._state)
            checked.update(
                state="error",
                lastCheckedAt=iso_time(self._clock()),
                operationStartedAt="",
                error="update_check_failed",
            )
        with self._lock:
            self._state = checked
            write_update_state(self.state_file, self._state)
            self._check_thread = None
        if automatic_install and checked["state"] == "available":
            try:
                self.start_update()
            except UpdateError:
                pass

    def _check_once(self) -> dict[str, Any]:
        checked_at = iso_time(self._clock())
        clean = self._git("status", "--porcelain", "--untracked-files=no", timeout=5)
        if clean.returncode != 0:
            raise UpdateError("update_check_failed")
        if clean.stdout.strip():
            return self._checked_state(
                state="modified",
                checked_at=checked_at,
                error="local_changes_prevent_update",
            )

        current = self._git("rev-parse", "HEAD", timeout=5)
        if current.returncode != 0:
            raise UpdateError("update_check_failed")
        fetched = self._git("fetch", "--quiet", "origin", "HEAD", timeout=20)
        if fetched.returncode != 0:
            raise UpdateError("update_check_failed")
        available = self._git("rev-parse", "FETCH_HEAD", timeout=5)
        if available.returncode != 0:
            raise UpdateError("update_check_failed")

        current_revision = current.stdout.strip()
        available_revision = available.stdout.strip()
        if current_revision == available_revision:
            return self._checked_state(
                state="current",
                checked_at=checked_at,
                current_revision=current_revision,
                available_revision=available_revision,
                available_version=VERSION,
            )

        ancestor = self._git(
            "merge-base", "--is-ancestor", "HEAD", "FETCH_HEAD", timeout=5
        )
        if ancestor.returncode != 0:
            return self._checked_state(
                state="diverged",
                checked_at=checked_at,
                current_revision=current_revision,
                available_revision=available_revision,
                error="update_history_diverged",
            )

        manifest = self._git("show", "FETCH_HEAD:manifest.json", timeout=5)
        available_version = self._manifest_version(manifest)
        return self._checked_state(
            state="available",
            checked_at=checked_at,
            current_revision=current_revision,
            available_revision=available_revision,
            available_version=available_version,
            update_available=True,
        )

    def _checked_state(
        self,
        *,
        state: str,
        checked_at: str,
        current_revision: str = "",
        available_revision: str = "",
        available_version: str = "",
        update_available: bool = False,
        error: str = "",
    ) -> dict[str, Any]:
        previous = dict(self._state)
        previous.update(
            state=state,
            availableVersion=available_version,
            currentRevision=current_revision,
            availableRevision=available_revision,
            lastCheckedAt=checked_at,
            operationStartedAt="",
            updateAvailable=update_available,
            error=error,
        )
        return previous

    def _set_error(self, code: str, *, state: str = "error") -> None:
        with self._lock:
            self._state.update(
                state=state,
                operationStartedAt="",
                error=code,
            )
            write_update_state(self.state_file, self._state)

    def _git(
        self, *arguments: str, timeout: int
    ) -> subprocess.CompletedProcess[str]:
        return self._run_command(
            [str(GIT), "-C", str(self.plugin_root), *arguments], timeout
        )

    @staticmethod
    def _manifest_version(
        result: subprocess.CompletedProcess[str],
    ) -> str:
        if result.returncode != 0 or len(result.stdout.encode("utf-8")) > 64 * 1024:
            raise UpdateError("update_check_failed")
        try:
            manifest = json.loads(result.stdout)
        except (json.JSONDecodeError, RecursionError) as error:
            raise UpdateError("update_check_failed") from error
        version = manifest.get("version") if isinstance(manifest, dict) else None
        plugin_id = manifest.get("id") if isinstance(manifest, dict) else None
        if (
            plugin_id != PLUGIN_ID
            or not isinstance(version, str)
            or not VERSION_PATTERN.fullmatch(version)
        ):
            raise UpdateError("update_check_failed")
        return version

    def _is_managed_install(self) -> bool:
        if self.plugin_root != self.installed_root:
            return False
        if not self.plugin_root.is_dir() or not (self.plugin_root / ".git").exists():
            return False
        if not GIT.is_file() or not OMARCHY.is_file() or not PYTHON.is_file():
            return False
        try:
            manifest = json.loads(
                (self.plugin_root / "manifest.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError, RecursionError):
            return False
        return isinstance(manifest, dict) and manifest.get("id") == PLUGIN_ID

    def _load_state(self) -> dict[str, Any]:
        default = default_update_state()
        if not self.state_file.exists():
            return default
        try:
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self.state_file, flags)
            try:
                info = os.fstat(descriptor)
                if (
                    info.st_uid != os.getuid()
                    or not stat.S_ISREG(info.st_mode)
                    or info.st_mode & 0o077
                    or info.st_size > MAX_UPDATE_STATE_BYTES
                ):
                    return default
                raw = os.read(descriptor, MAX_UPDATE_STATE_BYTES + 1)
            finally:
                os.close(descriptor)
            value = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            return default
        if not isinstance(value, dict):
            return default
        for key, fallback in default.items():
            candidate = value.get(key, fallback)
            if not isinstance(candidate, type(fallback)):
                return default
            default[key] = candidate
        if default["state"] == "checking":
            default["state"] = "idle"
            default["operationStartedAt"] = ""
        if default["state"] == "updating" and self._operation_is_stale(default):
            default["state"] = "error"
            default["operationStartedAt"] = ""
            default["error"] = "update_interrupted"
        return default

    def _operation_is_stale(self, state: dict[str, Any]) -> bool:
        started = self._parse_time(state.get("operationStartedAt", ""))
        return started is None or self._clock() - started > timedelta(minutes=10)

    def _check_is_stale(self, state: dict[str, Any]) -> bool:
        checked = self._parse_time(state.get("lastCheckedAt", ""))
        return checked is None or self._clock() - checked >= CHECK_INTERVAL

    @staticmethod
    def _parse_time(value: object) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed.astimezone(UTC) if parsed.tzinfo else None

    def _public_status(self, state: dict[str, Any]) -> dict[str, Any]:
        public_state = state["state"] if self._managed else "manual"
        return {
            "managed": self._managed,
            "state": public_state,
            "currentVersion": VERSION,
            "availableVersion": state["availableVersion"],
            "lastCheckedAt": state["lastCheckedAt"],
            "lastUpdatedAt": state["lastUpdatedAt"],
            "updateAvailable": bool(state["updateAvailable"]),
            "error": state["error"],
        }

from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import stat
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .updates import (
    GIT,
    OMARCHY,
    PLUGIN_ID,
    REVISION_PATTERN,
    VERSION_PATTERN,
    is_canonical_repository_url,
    iso_time,
    utc_now,
    write_update_state,
)


def _validated_version(plugin_root: Path) -> str:
    try:
        if (plugin_root / "manifest.json").stat().st_size > 64 * 1024:
            return ""
        manifest = json.loads(
            (plugin_root / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError, RecursionError):
        return ""
    version = manifest.get("version") if isinstance(manifest, dict) else None
    plugin_id = manifest.get("id") if isinstance(manifest, dict) else None
    return (
        version
        if plugin_id == PLUGIN_ID
        and isinstance(version, str)
        and len(version) <= 64
        and VERSION_PATTERN.fullmatch(version)
        else ""
    )


class InstallError(Exception):
    pass


def _git(plugin_root: Path, *arguments: str, timeout: int = 15) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(GIT_TERMINAL_PROMPT="0", GIT_NO_REPLACE_OBJECTS="1")
    return subprocess.run(
        [str(GIT), "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
         "-c", "submodule.recurse=false", "-C", str(plugin_root), *arguments],
        check=False, capture_output=True, text=True, timeout=timeout, env=environment,
    )


def _revision(plugin_root: Path, ref: str = "HEAD") -> str:
    result = _git(plugin_root, "rev-parse", "--verify", ref + "^{commit}")
    revision = result.stdout.strip()
    if result.returncode or not REVISION_PATTERN.fullmatch(revision):
        raise InstallError("update_revision_unavailable")
    return revision


def _origin_is_canonical(plugin_root: Path) -> bool:
    result = _git(plugin_root, "remote", "get-url", "origin")
    return result.returncode == 0 and is_canonical_repository_url(result.stdout)


def _clean(plugin_root: Path) -> bool:
    result = _git(plugin_root, "status", "--porcelain", "--untracked-files=all")
    return result.returncode == 0 and not result.stdout.strip()


def _validate(plugin_root: Path) -> str:
    version = _validated_version(plugin_root)
    if not version:
        raise InstallError("update_validation_failed")
    result = subprocess.run(
        [str(OMARCHY), "plugin", "validate", str(plugin_root)], check=False,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
    )
    if result.returncode:
        raise InstallError("update_validation_failed")
    return version


@contextmanager
def _install_lock(plugin_root: Path) -> Iterator[None]:
    descriptor = os.open(plugin_root / ".git" / "rock-arch-update.lock",
                         os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise InstallError("update_lock_unavailable")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise InstallError("update_already_running") from error
        yield
    finally:
        os.close(descriptor)


def _install_expected(plugin_root: Path, expected_revision: str) -> str:
    """Validate privately, then fast-forward using only an immutable object ID."""
    if not _clean(plugin_root):
        raise InstallError("local_changes_prevent_update")
    before = _revision(plugin_root)
    if _revision(plugin_root, expected_revision) != expected_revision:
        raise InstallError("update_revision_mismatch")
    if _git(plugin_root, "merge-base", "--is-ancestor", before, expected_revision).returncode:
        raise InstallError("update_history_diverged")

    with tempfile.TemporaryDirectory(prefix="rock-arch-update-") as temporary:
        staged = Path(temporary) / "candidate"
        try:
            added = _git(plugin_root, "worktree", "add", "--detach", str(staged), expected_revision, timeout=60)
            if added.returncode:
                raise InstallError("update_validation_failed")
            version = _validate(staged)
            if _revision(staged) != expected_revision or not _clean(staged):
                raise InstallError("update_revision_mismatch")
            # Recheck immediately before changing the watched installation.
            if not _origin_is_canonical(plugin_root) or _revision(plugin_root) != before or not _clean(plugin_root):
                raise InstallError("update_checkout_changed")
            if _revision(plugin_root, expected_revision) != expected_revision:
                raise InstallError("update_revision_mismatch")
            merged = _git(plugin_root, "merge", "--ff-only", "--no-edit", "--no-overwrite-ignore", expected_revision, timeout=60)
            if merged.returncode:
                raise InstallError("update_failed")
            # Only the previously validated commit is installed; never follow a ref
            # or run Omarchy's updater, which fetches mutable remote HEAD again.
            if _revision(plugin_root) != expected_revision or not _clean(plugin_root):
                raise InstallError("update_revision_mismatch")
            if _validate(plugin_root) != version or _revision(plugin_root) != expected_revision or not _clean(plugin_root):
                raise InstallError("update_validation_failed")
            return version
        finally:
            _git(plugin_root, "worktree", "remove", "--force", str(staged), timeout=30)


def _notify(message: str) -> None:
    notifier = Path("/usr/bin/notify-send")
    if not notifier.is_file():
        return
    try:
        subprocess.run(
            [str(notifier), "Rock Arch", message],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _terminate_broker(parent_pid: int) -> None:
    if parent_pid <= 1 or parent_pid == os.getpid():
        return
    process_root = Path("/proc") / str(parent_pid)
    try:
        if process_root.stat().st_uid != os.getuid():
            return
        command_line = (process_root / "cmdline").read_bytes()[:4096]
        if b"rock_arch_broker" not in command_line:
            return
        os.kill(parent_pid, signal.SIGTERM)
    except (OSError, ValueError):
        pass


def run_update(state_file: Path, plugin_root: Path, parent_pid: int, expected_revision: str) -> int:
    expected_root = Path.home() / ".config/omarchy/plugins" / PLUGIN_ID
    state: dict[str, Any] = {
        "state": "error", "availableVersion": "", "currentRevision": "",
        "availableRevision": "", "lastCheckedAt": iso_time(utc_now()),
        "lastUpdatedAt": "", "operationStartedAt": "", "updateAvailable": False,
        "error": "update_failed",
    }
    try:
        if not isinstance(expected_revision, str) or not REVISION_PATTERN.fullmatch(expected_revision):
            raise InstallError("update_check_required")
        state["availableRevision"] = expected_revision
        if (plugin_root != expected_root or plugin_root.resolve() != expected_root
                or (plugin_root / ".git").is_symlink()
                or not (plugin_root / ".git").is_dir() or not _validated_version(plugin_root)):
            raise InstallError("update_managed_manually")
        if not _origin_is_canonical(plugin_root):
            raise InstallError("update_source_not_allowed")
        with _install_lock(plugin_root):
            version = _install_expected(plugin_root, expected_revision)
            # Last identity check before explicitly activating the new plugin.
            if _revision(plugin_root) != expected_revision or not _clean(plugin_root):
                raise InstallError("update_revision_mismatch")
            restarted = subprocess.run(
                [str(OMARCHY), "restart", "shell"], check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
            )
            if restarted.returncode:
                _terminate_broker(parent_pid)
                raise InstallError("update_restart_failed")
            if _revision(plugin_root) != expected_revision:
                raise InstallError("update_revision_mismatch")
            state.update(state="updated", availableVersion=version,
                         currentRevision=expected_revision, lastUpdatedAt=iso_time(utc_now()), error="")
            write_update_state(state_file, state)
            _notify(f"Updated to {version}.")
            _terminate_broker(parent_pid)
            return 0
    except InstallError as error:
        state["error"] = str(error)
    except (OSError, UnicodeError, subprocess.SubprocessError):
        state["error"] = "update_failed"
    write_update_state(state_file, state)
    _notify("The update did not finish. Open Settings to check again.")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Install the exact checked Rock Arch commit")
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--plugin-root", type=Path, required=True)
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("--expected-revision", required=True)
    arguments = parser.parse_args()
    raise SystemExit(run_update(arguments.state_file, arguments.plugin_root,
                                arguments.parent_pid, arguments.expected_revision))


if __name__ == "__main__":
    main()

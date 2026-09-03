from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
from pathlib import Path
from typing import Any

from .updates import (
    GIT,
    OMARCHY,
    PLUGIN_ID,
    VERSION_PATTERN,
    iso_time,
    utc_now,
    write_update_state,
)


def _validated_version(plugin_root: Path) -> str:
    try:
        manifest = json.loads(
            (plugin_root / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError, RecursionError):
        return ""
    version = manifest.get("version") if isinstance(manifest, dict) else None
    plugin_id = manifest.get("id") if isinstance(manifest, dict) else None
    return (
        version
        if plugin_id == PLUGIN_ID
        and isinstance(version, str)
        and VERSION_PATTERN.fullmatch(version)
        else ""
    )


def _revision(plugin_root: Path) -> str:
    try:
        result = subprocess.run(
            [str(GIT), "-C", str(plugin_root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


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
        if b"rock_lens_broker" not in command_line:
            return
        os.kill(parent_pid, signal.SIGTERM)
    except (OSError, ValueError):
        pass


def run_update(state_file: Path, plugin_root: Path, parent_pid: int) -> int:
    expected_root = (
        Path.home() / ".config/omarchy/plugins" / PLUGIN_ID
    ).resolve()
    plugin_root = plugin_root.resolve()
    now = iso_time(utc_now())
    if (
        plugin_root != expected_root
        or not (plugin_root / ".git").exists()
        or not _validated_version(plugin_root)
    ):
        write_update_state(
            state_file,
            {
                "state": "error",
                "availableVersion": "",
                "currentRevision": "",
                "availableRevision": "",
                "lastCheckedAt": now,
                "lastUpdatedAt": "",
                "operationStartedAt": "",
                "updateAvailable": False,
                "error": "update_managed_manually",
            },
        )
        return 1

    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment.setdefault("GIT_SSH_COMMAND", "ssh -oBatchMode=yes")
    try:
        result = subprocess.run(
            [str(OMARCHY), "plugin", "update", PLUGIN_ID, "--yes"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=180,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError):
        result = None

    completed_at = iso_time(utc_now())
    if result is None or result.returncode != 0:
        write_update_state(
            state_file,
            {
                "state": "error",
                "availableVersion": "",
                "currentRevision": "",
                "availableRevision": "",
                "lastCheckedAt": completed_at,
                "lastUpdatedAt": "",
                "operationStartedAt": "",
                "updateAvailable": False,
                "error": "update_failed",
            },
        )
        _notify("The update did not finish. Open Settings to try again.")
        return 1

    try:
        restarted = subprocess.run(
            [str(OMARCHY), "restart", "shell"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError):
        restarted = None
    if restarted is None or restarted.returncode != 0:
        write_update_state(
            state_file,
            {
                "state": "error",
                "availableVersion": "",
                "currentRevision": "",
                "availableRevision": "",
                "lastCheckedAt": completed_at,
                "lastUpdatedAt": "",
                "operationStartedAt": "",
                "updateAvailable": False,
                "error": "update_failed",
            },
        )
        _notify("The update installed, but the shell did not restart.")
        _terminate_broker(parent_pid)
        return 1

    version = _validated_version(plugin_root)
    revision = _revision(plugin_root)
    state: dict[str, Any] = {
        "state": "updated",
        "availableVersion": version,
        "currentRevision": revision,
        "availableRevision": revision,
        "lastCheckedAt": completed_at,
        "lastUpdatedAt": completed_at,
        "operationStartedAt": "",
        "updateAvailable": False,
        "error": "",
    }
    write_update_state(state_file, state)
    _notify(f"Updated to {version}." if version else "Update installed.")
    _terminate_broker(parent_pid)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Complete a fixed Rock Arch update")
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--plugin-root", type=Path, required=True)
    parser.add_argument("--parent-pid", type=int, required=True)
    arguments = parser.parse_args()
    raise SystemExit(
        run_update(arguments.state_file, arguments.plugin_root, arguments.parent_pid)
    )


if __name__ == "__main__":
    main()

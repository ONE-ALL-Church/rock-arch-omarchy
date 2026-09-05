from __future__ import annotations

import subprocess
from pathlib import Path

NOTIFY_SEND = Path("/usr/bin/notify-send")


def notify_build_accepted() -> bool:
    """Send a privacy-minimized local notification, when supported."""

    if not NOTIFY_SEND.is_file():
        return False
    try:
        completed = subprocess.run(
            [
                str(NOTIFY_SEND),
                "--app-name=Rock Arch",
                "Rock Arch",
                "Magnus accepted the deployment request.",
            ],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0

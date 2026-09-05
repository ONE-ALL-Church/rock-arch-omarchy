from __future__ import annotations

import subprocess
from pathlib import Path

WL_COPY = Path("/usr/bin/wl-copy")


def copy_to_clipboard(value: str) -> bool:
    """Copy text through stdin so content never appears in argv."""

    if not WL_COPY.is_file():
        return False
    try:
        result = subprocess.run(
            [str(WL_COPY)],
            input=value.encode("utf-8"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0

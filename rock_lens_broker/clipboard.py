from __future__ import annotations

import shutil
import subprocess


def copy_to_clipboard(value: str) -> bool:
    """Copy text through stdin so content never appears in argv."""

    executable = shutil.which("wl-copy")
    if not executable:
        return False
    try:
        result = subprocess.run(
            [executable],
            input=value.encode("utf-8"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0

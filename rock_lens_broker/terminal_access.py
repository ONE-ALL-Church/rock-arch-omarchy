from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any

CLI_CLIENT = "rock-arch-cli"
CLI_LAUNCHER_MARKER = (
    "# Managed by Rock Arch; terminal access is controlled in Settings."
)
MAX_LAUNCHER_BYTES = 16 * 1024
PLUGIN_ID = "oneall.rock-arch"


def default_launcher_path() -> Path:
    return Path.home() / ".local/bin/rock-arch"


def render_launcher(plugin_root: Path) -> bytes:
    root = json.dumps(str(plugin_root.resolve()))
    return (
        "#!/usr/bin/python3\n"
        f"{CLI_LAUNCHER_MARKER}\n"
        "import sys\n"
        f"sys.path.insert(0, {root})\n"
        "from rock_lens_broker.cli import main\n"
        "main()\n"
    ).encode()


class TerminalAccessManager:
    """Install and report the owner-local Rock Arch command launcher."""

    def __init__(
        self,
        plugin_root: Path | None = None,
        launcher_path: Path | None = None,
        installed_root: Path | None = None,
    ) -> None:
        self.plugin_root = (
            plugin_root or Path(__file__).resolve().parents[1]
        ).resolve()
        self.launcher_path = launcher_path or default_launcher_path()
        self.installed_root = (
            installed_root or Path.home() / ".config/omarchy/plugins" / PLUGIN_ID
        ).resolve()
        self._error = ""

    def ensure_launcher(self) -> None:
        if self.plugin_root != self.installed_root:
            self._error = "cli_launcher_managed_manually"
            return
        desired = render_launcher(self.plugin_root)
        try:
            self._validate_parent()
            existing = self._read_existing()
            if existing == desired:
                self.launcher_path.chmod(0o755)
                self._error = ""
                return
            managed_prefix = (
                "#!/usr/bin/python3\n" + CLI_LAUNCHER_MARKER + "\n"
            ).encode()
            if existing is not None and not existing.startswith(managed_prefix):
                self._error = "cli_launcher_conflict"
                return
            self._replace(desired)
            self._error = ""
        except OSError:
            self._error = "cli_launcher_unavailable"

    def status(self, *, enabled: bool) -> dict[str, Any]:
        installed = False
        try:
            installed = self._read_existing() == render_launcher(self.plugin_root)
        except OSError:
            if not self._error:
                self._error = "cli_launcher_unavailable"
        resolved = shutil.which("rock-arch")
        return {
            "enabled": enabled,
            "installed": installed,
            "command": "rock-arch",
            "path": str(self.launcher_path),
            "inPath": bool(
                installed
                and resolved
                and Path(resolved).resolve() == self.launcher_path.resolve()
            ),
            "error": self._error,
        }

    def _validate_parent(self) -> None:
        parent = self.launcher_path.parent
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = os.lstat(parent)
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o022
        ):
            raise OSError("unsafe launcher directory")

    def _read_existing(self) -> bytes | None:
        try:
            info = os.lstat(self.launcher_path)
        except FileNotFoundError:
            return None
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_size > MAX_LAUNCHER_BYTES
        ):
            raise OSError("unsafe launcher path")
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.launcher_path, flags)
        try:
            return os.read(descriptor, MAX_LAUNCHER_BYTES + 1)
        finally:
            os.close(descriptor)

    def _replace(self, content: bytes) -> None:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".rock-arch-", dir=self.launcher_path.parent
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o755)
            with os.fdopen(descriptor, "wb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.launcher_path)
            self.launcher_path.chmod(0o755)
        finally:
            temporary.unlink(missing_ok=True)


class UnmanagedTerminalAccess:
    """No-write terminal status used by embedded and test brokers."""

    def ensure_launcher(self) -> None:
        return None

    @staticmethod
    def status(*, enabled: bool) -> dict[str, Any]:
        return {
            "enabled": enabled,
            "installed": False,
            "command": "rock-arch",
            "path": "",
            "inPath": False,
            "error": "",
        }

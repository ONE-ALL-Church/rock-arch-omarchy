from __future__ import annotations

import shutil
import subprocess
from typing import Protocol

from .contracts import Context

SECRET_TOOL_TIMEOUT_SECONDS = 10


class SecretStoreError(Exception):
    """A stable failure from the desktop password manager."""


class SecretStore(Protocol):
    def available(self) -> bool: ...

    def lookup(self, context: Context, kind: str) -> str | None: ...

    def store(self, context: Context, kind: str, value: str) -> None: ...

    def clear(self, context: Context, kind: str) -> bool: ...


class SecretToolStore:
    """Secret Service storage that never puts secret values in argv or logs."""

    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or shutil.which("secret-tool") or ""

    def available(self) -> bool:
        return bool(self.executable)

    def _attributes(self, context: Context, kind: str) -> list[str]:
        # Stable keyring namespace: changing this would orphan saved logins.
        return ["application", "rock-lens", "context", context.value, "kind", kind]

    def lookup(self, context: Context, kind: str) -> str | None:
        if not self.available():
            return None
        try:
            result = subprocess.run(
                [self.executable, "lookup", *self._attributes(context, kind)],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=SECRET_TOOL_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return (
            result.stdout.decode("utf-8").rstrip("\n")
            if result.returncode == 0 and result.stdout
            else None
        )

    def store(self, context: Context, kind: str, value: str) -> None:
        if not self.available():
            raise SecretStoreError("secure_storage_unavailable")
        try:
            result = subprocess.run(
                [
                    self.executable,
                    "store",
                    f"--label=Rock Arch {context.value} {kind}",
                    *self._attributes(context, kind),
                ],
                input=value.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=SECRET_TOOL_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SecretStoreError("secure_storage_failed") from error
        if result.returncode != 0:
            raise SecretStoreError("secure_storage_failed")

    def clear(self, context: Context, kind: str) -> bool:
        if not self.available():
            return False
        attributes = self._attributes(context, kind)
        try:
            result = subprocess.run(
                [self.executable, "clear", *attributes],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=SECRET_TOOL_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        if result.returncode == 0:
            return True

        # `secret-tool clear` exits 1 without diagnostic output when no item
        # matched. Confirm that absence with an independent lookup so cleanup
        # remains idempotent without masking a locked or failing keyring.
        if result.returncode != 1 or result.stderr:
            return False
        try:
            lookup = subprocess.run(
                [self.executable, "lookup", *attributes],
                capture_output=True,
                timeout=SECRET_TOOL_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return (
            lookup.returncode == 1
            and not lookup.stdout
            and not lookup.stderr
        )

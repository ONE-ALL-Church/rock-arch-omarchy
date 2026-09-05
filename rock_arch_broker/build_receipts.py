from __future__ import annotations

import json
import os
import secrets
import stat
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import sanitize_text

MAX_BUILD_RECEIPTS = 50
MAX_STORE_BYTES = 128 * 1024


class BuildReceiptStore:
    """Owner-only local receipts for Magnus requests accepted by the server."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def add(self, title: object) -> dict[str, Any]:
        receipt = {
            "buildId": "build-" + secrets.token_hex(16),
            "title": sanitize_text(title, 160) or "Magnus mobile app",
            "state": "accepted",
            "acceptedAt": datetime.now(UTC).isoformat(timespec="seconds").replace(
                "+00:00", "Z"
            ),
            "message": "Magnus accepted the deployment request.",
            "statusSource": "local",
            "completionVerifiable": False,
            "persisted": True,
        }
        rows = self._read()
        rows.append(receipt)
        try:
            self._write(rows[-MAX_BUILD_RECEIPTS:])
        except OSError:
            receipt["persisted"] = False
        return dict(receipt)

    def public_items(self) -> list[dict[str, Any]]:
        return list(reversed(self._read()))

    def get(self, build_id: object) -> dict[str, Any] | None:
        candidate = sanitize_text(build_id, 100)
        for row in self._read():
            if secrets.compare_digest(str(row["buildId"]), candidate):
                return dict(row)
        return None

    def clear(self) -> bool:
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            return False
        return True

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self.path, flags)
            try:
                info = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.getuid()
                    or info.st_mode & 0o077
                    or info.st_size > MAX_STORE_BYTES
                ):
                    return []
                raw = os.read(descriptor, MAX_STORE_BYTES + 1)
            finally:
                os.close(descriptor)
            value = json.loads(raw)
        except (OSError, ValueError, RecursionError):
            return []
        if not isinstance(value, list):
            return []
        rows: list[dict[str, Any]] = []
        for item in value[-MAX_BUILD_RECEIPTS:]:
            row = self._validated(item)
            if row:
                rows.append(row)
        return rows

    @staticmethod
    def _validated(value: object) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        build_id = sanitize_text(value.get("buildId"), 100)
        title = sanitize_text(value.get("title"), 160)
        accepted_at = sanitize_text(value.get("acceptedAt"), 64)
        suffix = build_id.removeprefix("build-")
        if (
            not build_id.startswith("build-")
            or len(suffix) != 32
            or any(character not in "0123456789abcdef" for character in suffix)
            or not title
        ):
            return None
        try:
            datetime.fromisoformat(accepted_at)
        except ValueError:
            return None
        return {
            "buildId": build_id,
            "title": title,
            "state": "accepted",
            "acceptedAt": accepted_at,
            "message": "Magnus accepted the deployment request.",
            "statusSource": "local",
            "completionVerifiable": False,
            "persisted": True,
        }

    def _write(self, rows: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path.parent.chmod(0o700)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".build-receipts-", dir=self.path.parent
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(rows, output, separators=(",", ":"), ensure_ascii=True)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
            self.path.chmod(0o600)
        finally:
            temporary.unlink(missing_ok=True)

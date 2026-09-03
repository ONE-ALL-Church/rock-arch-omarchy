from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import stat
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import ALLOWED_QUICK_RETURN_KEYS, allowlist, sanitize_text
from .navigation import NavigationError, NavigationTarget, clean_target
from .origin import OriginError, validate_rock_origin

MAX_QUICK_RETURNS = 20
MAX_STORE_BYTES = 128 * 1024


class QuickReturnStore:
    """Owner-only launcher history that mirrors Rock's 20-item quick-return cap."""

    def __init__(self, path: Path, origin: str | None = None) -> None:
        self.path = path
        self.origin = validate_rock_origin(origin) if origin else ""
        self._key = secrets.token_bytes(32)

    def set_origin(self, origin: str) -> None:
        try:
            self.origin = validate_rock_origin(origin)
        except OriginError as error:
            raise NavigationError("invalid_rock_origin") from error

    def public_items(self) -> list[dict[str, Any]]:
        if not self.origin:
            return []
        rows = sorted(
            self._read(),
            key=lambda row: datetime.fromisoformat(
                str(row["createdDateTime"])
            ).timestamp(),
            reverse=True,
        )
        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(
                allowlist(
                    {
                        "safeId": self._safe_id(row),
                        "title": row["title"],
                        "kind": row["kind"],
                        "lastUsedAt": row["createdDateTime"],
                    },
                    ALLOWED_QUICK_RETURN_KEYS,
                )
            )
        return result

    def add(self, target: NavigationTarget) -> None:
        if not self.origin:
            raise NavigationError("invalid_rock_origin")
        clean = clean_target(
            target.title, target.kind, target.type_order, target.url, self.origin
        )
        rows = [
            row
            for row in self._read()
            if not (
                str(row["kind"]).casefold() == clean.kind.casefold()
                and str(row["url"]).casefold() == clean.url.casefold()
            )
            and not (
                str(row["kind"]).casefold() == clean.kind.casefold()
                and int(row["typeOrder"]) == clean.type_order
                and str(row["title"]).casefold() == clean.title.casefold()
            )
        ]
        rows.append(
            {
                "title": clean.title,
                "kind": clean.kind,
                "typeOrder": clean.type_order,
                "url": clean.url,
                "createdDateTime": datetime.now(UTC).isoformat(),
            }
        )
        self._write(rows[-MAX_QUICK_RETURNS:])

    def resolve(self, safe_id: str) -> NavigationTarget | None:
        if not self.origin:
            return None
        candidate = sanitize_text(safe_id, 100)
        for row in self._read():
            if hmac.compare_digest(self._safe_id(row), candidate):
                try:
                    return clean_target(
                        row["title"],
                        row["kind"],
                        int(row["typeOrder"]),
                        row["url"],
                        self.origin,
                    )
                except (NavigationError, TypeError, ValueError):
                    return None
        return None

    def clear(self) -> bool:
        """Clear the active profile's local history."""

        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            return False
        return True

    def migrate_from(self, path: Path) -> None:
        """Copy validated legacy history while retaining the source as rollback."""

        if self.path.exists() or path == self.path:
            return
        rows = QuickReturnStore(path, self.origin)._read()
        if rows:
            self._write(rows)

    def _safe_id(self, row: dict[str, Any]) -> str:
        message = f"{row['kind']}\0{row['url']}".encode()
        return "quick-" + hmac.new(self._key, message, hashlib.sha256).hexdigest()[:32]

    def _read(self) -> list[dict[str, Any]]:
        if not self.origin or not self.path.exists():
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
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            return []
        if not isinstance(value, list):
            return []

        rows: list[dict[str, Any]] = []
        for item in value[-MAX_QUICK_RETURNS:]:
            if not isinstance(item, dict):
                continue
            try:
                target = clean_target(
                    item.get("title"),
                    item.get("kind"),
                    int(item.get("typeOrder")),
                    item.get("url"),
                    self.origin,
                )
                created = sanitize_text(item.get("createdDateTime"), 64)
                datetime.fromisoformat(created)
            except (NavigationError, TypeError, ValueError):
                continue
            rows.append(
                {
                    "title": target.title,
                    "kind": target.kind,
                    "typeOrder": target.type_order,
                    "url": target.url,
                    "createdDateTime": created,
                }
            )
        return rows

    def _write(self, rows: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path.parent.chmod(0o700)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".quick-returns-", dir=self.path.parent
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

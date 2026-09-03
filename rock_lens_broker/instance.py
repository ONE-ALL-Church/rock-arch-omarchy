from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from .origin import OriginError, validate_rock_origin


def default_instance_path() -> Path:
    return (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "rock-arch"
        / "instance.json"
    )


class InstanceStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self) -> str | None:
        try:
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self.path, flags)
            try:
                info = os.fstat(descriptor)
                if (
                    info.st_uid != os.getuid()
                    or not stat.S_ISREG(info.st_mode)
                    or info.st_mode & 0o077
                    or info.st_size > 4_096
                ):
                    return None
                raw = os.read(descriptor, 4_097)
            finally:
                os.close(descriptor)
            value = json.loads(raw)
            origin = value.get("origin") if isinstance(value, dict) else None
            return validate_rock_origin(origin)
        except (OSError, OriginError, json.JSONDecodeError, RecursionError):
            return None

    def set(self, value: object) -> str:
        origin = validate_rock_origin(value)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path.parent.chmod(0o700)
        temporary = self.path.with_name(self.path.name + ".tmp")
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump({"origin": origin}, output, separators=(",", ":"))
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, self.path)
        self.path.chmod(0o600)
        return origin

    def clear(self) -> None:
        """Remove the legacy active-instance pointer without following links."""

        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            return

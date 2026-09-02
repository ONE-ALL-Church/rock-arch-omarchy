from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import urllib.parse
from pathlib import Path, PurePosixPath
from typing import Any

from .auth import SecretStore, SecretToolStore
from .contracts import Context, sanitize_text

CANONICAL_MAGNUS_SERVER = "https://rock.example.org"
DEFAULT_TREE_PATH = "api/TriumphTech/Magnus/GetTreeItems/root"
TREE_PATH_PREFIX = "api/TriumphTech/Magnus/GetTreeItems/"
FILE_PATH_PREFIX = "/FileContent/"
MAX_TREE_ITEMS = 500
MAX_TREE_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_FILE_BYTES = 4 * 1024 * 1024


class MagnusError(Exception):
    """A stable local error that never includes credentials or response bodies."""


def validate_magnus_server(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    canonical = urllib.parse.urlsplit(CANONICAL_MAGNUS_SERVER)
    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname != canonical.hostname
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise MagnusError("magnus_server_not_allowed")
    return CANONICAL_MAGNUS_SERVER


def validate_tree_path(value: str) -> str:
    path = value.strip().lstrip("/")
    if (
        not path.startswith(TREE_PATH_PREFIX)
        or len(path) == len(TREE_PATH_PREFIX)
        or "://" in path
        or "?" in path
        or "#" in path
        or "\\" in path
        or len(path) > 800
        or any(ord(char) < 32 for char in path)
    ):
        raise MagnusError("invalid_magnus_tree_path")
    if any(part in ("", ".", "..") for part in PurePosixPath(path).parts):
        raise MagnusError("invalid_magnus_tree_path")
    return path


def validate_file_path(value: str) -> str:
    path = value.strip()
    if (
        not path.startswith(FILE_PATH_PREFIX)
        or len(path) == len(FILE_PATH_PREFIX)
        or "://" in path
        or "?" in path
        or "#" in path
        or "\\" in path
        or len(path) > 800
        or any(ord(char) < 32 for char in path)
    ):
        raise MagnusError("invalid_magnus_file_path")
    if any(part in (".", "..") for part in PurePosixPath(path).parts):
        raise MagnusError("invalid_magnus_file_path")
    return path


class MagnusReadOnlyAdapter:
    """Hardened read-only boundary around the installed Magnus CLI."""

    def __init__(
        self,
        server: str = CANONICAL_MAGNUS_SERVER,
        executable: str | None = None,
        secret_store: SecretStore | None = None,
        context: Context = Context.PROD,
    ) -> None:
        self.server = validate_magnus_server(server)
        self.executable = executable or shutil.which("magnus") or ""
        self.secret_store = secret_store or SecretToolStore()
        self.context = context

    def status(self) -> dict[str, Any]:
        available = bool(self.executable) and self.secret_store.available()
        configured = available and bool(self._credentials())
        return {
            "available": available,
            "configured": configured,
            "mode": "read_only",
            "server": "rock.example.org",
        }

    def configure(self, username: str, password: str) -> None:
        normalized_username = username.strip()
        if (
            not normalized_username
            or len(normalized_username) > 200
            or any(ord(char) < 32 for char in normalized_username)
        ):
            raise MagnusError("invalid_magnus_username")
        if not password or len(password) > 4_096 or "\x00" in password:
            raise MagnusError("invalid_magnus_password")
        if not self.secret_store.available():
            raise MagnusError("secure_storage_unavailable")
        try:
            self.secret_store.store(
                self.context, "magnus_username", normalized_username
            )
            self.secret_store.store(self.context, "magnus_password", password)
        except Exception as error:
            self.secret_store.clear(self.context, "magnus_username")
            self.secret_store.clear(self.context, "magnus_password")
            raise MagnusError("secure_storage_failed") from error

    def list_tree(self, path: str = DEFAULT_TREE_PATH) -> list[dict[str, Any]]:
        safe_path = validate_tree_path(path)
        output = self._run(["ls", "--long", "--json", safe_path], MAX_TREE_OUTPUT_BYTES)
        try:
            value = json.loads(output)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise MagnusError("invalid_magnus_response") from error
        if not isinstance(value, list) or len(value) > MAX_TREE_ITEMS:
            raise MagnusError("magnus_response_out_of_bounds")
        return [self._sanitize_tree_item(item) for item in value]

    def read_file(self, path: str) -> bytes:
        safe_path = validate_file_path(path)
        return self._run(["cat", safe_path], MAX_FILE_BYTES)

    def hash_file(self, path: str) -> str:
        return hashlib.sha256(self.read_file(path)).hexdigest()

    def _credentials(self) -> tuple[str, str] | None:
        username = self.secret_store.lookup(self.context, "magnus_username")
        password = self.secret_store.lookup(self.context, "magnus_password")
        return (username, password) if username and password else None

    def _run(self, command: list[str], maximum_bytes: int) -> bytes:
        if not self.executable or not self.secret_store.available():
            raise MagnusError("magnus_unavailable")
        credentials = self._credentials()
        if not credentials:
            raise MagnusError("magnus_not_configured")
        username, password = credentials

        runtime_parent = Path(
            os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        )
        if not runtime_parent.is_dir():
            runtime_parent = Path("/tmp")
        with tempfile.TemporaryDirectory(
            prefix="rock-lens-magnus-", dir=runtime_parent
        ) as temporary:
            config_home = Path(temporary)
            config_home.chmod(0o700)
            environment = os.environ.copy()
            environment["XDG_CONFIG_HOME"] = str(config_home)
            environment["NO_COLOR"] = "1"

            try:
                login = subprocess.run(
                    [
                        self.executable,
                        "login",
                        self.server,
                        "--username",
                        username,
                        "--default",
                    ],
                    input=(password + "\n").encode("utf-8"),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=20,
                    check=False,
                    env=environment,
                )
            except (OSError, subprocess.TimeoutExpired) as error:
                raise MagnusError("magnus_login_failed") from error
            if login.returncode != 0:
                raise MagnusError("magnus_login_failed")
            self._harden_temporary_files(config_home)

            output_path = config_home / "rock-lens-output"
            flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(output_path, flags, 0o600)
            with os.fdopen(descriptor, "w+b") as output:
                try:
                    result = subprocess.run(
                        [self.executable, *command, "--server", self.server],
                        stdin=subprocess.DEVNULL,
                        stdout=output,
                        stderr=subprocess.DEVNULL,
                        timeout=30,
                        check=False,
                        env=environment,
                    )
                except (OSError, subprocess.TimeoutExpired) as error:
                    raise MagnusError("magnus_request_failed") from error
                self._harden_temporary_files(config_home)
                if result.returncode != 0:
                    raise MagnusError("magnus_request_failed")
                size = output.tell()
                if size > maximum_bytes:
                    raise MagnusError("magnus_response_out_of_bounds")
                output.seek(0)
                return output.read()

    @staticmethod
    def _harden_temporary_files(root: Path) -> None:
        for path in root.rglob("*"):
            try:
                path.chmod(0o700 if path.is_dir() else 0o600)
            except OSError:
                pass

    @staticmethod
    def _sanitize_tree_item(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise MagnusError("invalid_magnus_response")
        item: dict[str, Any] = {
            "displayName": sanitize_text(value.get("displayName"), 200),
            "isFolder": bool(value.get("isFolder")),
        }
        for key in ("id", "guid"):
            if value.get(key) is not None:
                item[key] = sanitize_text(value.get(key), 100)
        for source, target, validator in (
            ("path", "path", validate_tree_path),
            ("uri", "path", validate_tree_path),
            ("filePath", "filePath", validate_file_path),
            ("fileContentUri", "filePath", validate_file_path),
        ):
            raw = value.get(source)
            if isinstance(raw, str):
                try:
                    item[target] = validator(raw)
                except MagnusError:
                    pass
        return item

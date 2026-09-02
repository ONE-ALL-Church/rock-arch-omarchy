from __future__ import annotations

import hashlib
import json
import os
import select
import shutil
import stat
import subprocess
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any

from .auth import SecretStore, SecretToolStore
from .contracts import Context, sanitize_text
from .origin import DEFAULT_ROCK_ORIGIN, OriginError, validate_rock_origin
from .profiles import ProfileError, validate_profile_id

CANONICAL_MAGNUS_SERVER = DEFAULT_ROCK_ORIGIN
DEFAULT_TREE_PATH = "api/TriumphTech/Magnus/GetTreeItems/root"
TREE_PATH_PREFIX = "api/TriumphTech/Magnus/GetTreeItems/"
FILE_PATH_PREFIX = "/FileContent/"
MAX_TREE_ITEMS = 500
MAX_TREE_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_COOKIE_CONFIG_BYTES = 64 * 1024
MAX_COOKIE_CONFIG_NODES = 1_024
MAX_COOKIE_CONFIG_DEPTH = 16
MAX_PASSWORD_BYTES = 1_024
PASSWORD_PROMPT_TIMEOUT_SECONDS = 5
PASSWORD_KEYSTROKE_DELAY_SECONDS = 0.01
AUTH_COOKIE_IDLE_SECONDS = 15 * 60


class MagnusError(Exception):
    """A stable local error that never includes credentials or response bodies."""


def validate_magnus_server(value: str) -> str:
    try:
        return validate_rock_origin(value)
    except OriginError as error:
        raise MagnusError("magnus_server_not_allowed") from error


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
        server: str | None = None,
        executable: str | None = None,
        secret_store: SecretStore | None = None,
        context: Context = Context.PROD,
        profile_id: str | None = None,
    ) -> None:
        self.server = validate_magnus_server(server) if server else ""
        self.executable = executable or shutil.which("magnus") or ""
        self.secret_store = secret_store or SecretToolStore()
        self.context = context
        try:
            self.profile_id = validate_profile_id(profile_id) if profile_id else ""
        except ProfileError as error:
            raise MagnusError("invalid_profile") from error
        self._cached_cookie = ""
        self._cached_cookie_deadline = 0.0
        self._cache_generation = 0
        self._cache_lock = threading.Lock()
        self._cache_timer: threading.Timer | None = None

    def status(self) -> dict[str, Any]:
        available = bool(self.executable) and self.secret_store.available()
        configured = (
            available
            and bool(self.server)
            and (self._has_cached_cookie() or bool(self._credentials()))
        )
        return {
            "available": available,
            "configured": configured,
            "mode": "read_only",
            "server": self.server.removeprefix("https://"),
        }

    def set_server(self, value: str) -> None:
        server = validate_magnus_server(value)
        if server != self.server:
            self._clear_cached_cookie()
        self.server = server

    def set_profile(self, profile_id: str, server: str) -> None:
        try:
            safe_profile_id = validate_profile_id(profile_id)
        except ProfileError as error:
            raise MagnusError("invalid_profile") from error
        safe_server = validate_magnus_server(server)
        if safe_profile_id != self.profile_id or safe_server != self.server:
            self._clear_cached_cookie()
        self.profile_id = safe_profile_id
        self.server = safe_server

    def clear_profile(self) -> None:
        self._clear_cached_cookie()
        self.profile_id = ""
        self.server = ""

    def configure(self, username: str, password: str) -> None:
        if not self.server:
            raise MagnusError("magnus_server_not_configured")
        normalized_username = username.strip()
        if (
            not normalized_username
            or len(normalized_username) > 200
            or any(ord(char) < 32 for char in normalized_username)
        ):
            raise MagnusError("invalid_magnus_username")
        if (
            not password
            or len(password.encode("utf-8")) > MAX_PASSWORD_BYTES
            or any(char in password for char in "\x00\r\n")
        ):
            raise MagnusError("invalid_magnus_password")
        if not self.secret_store.available():
            raise MagnusError("secure_storage_unavailable")
        try:
            self.secret_store.store(
                self.context,
                self._secret_kind("magnus_username"),
                normalized_username,
            )
            self.secret_store.store(
                self.context, self._secret_kind("magnus_password"), password
            )
        except Exception as error:
            self.secret_store.clear(self.context, self._secret_kind("magnus_username"))
            self.secret_store.clear(self.context, self._secret_kind("magnus_password"))
            raise MagnusError("secure_storage_failed") from error
        self._clear_cached_cookie()

    def migrate_legacy_credentials(self) -> bool:
        """Copy origin-keyed credentials into the active profile key once."""

        if not self.profile_id or not self.server or not self.secret_store.available():
            return False
        if self._credentials():
            return False
        username = self.secret_store.lookup(
            self.context, self._legacy_secret_kind("magnus_username")
        )
        password = self.secret_store.lookup(
            self.context, self._legacy_secret_kind("magnus_password")
        )
        if not username or not password:
            return False
        try:
            self.secret_store.store(
                self.context, self._secret_kind("magnus_username"), username
            )
            self.secret_store.store(
                self.context, self._secret_kind("magnus_password"), password
            )
        except Exception as error:
            self._clear_profile_keys(self.profile_id)
            raise MagnusError("secure_storage_failed") from error
        if self._credentials() != (username, password):
            self._clear_profile_keys(self.profile_id)
            raise MagnusError("secure_storage_failed")
        return True

    def sign_out(self) -> None:
        """Clear credentials and the memory-only cookie for the active profile."""

        if self.profile_id:
            self._clear_profile_keys(self.profile_id)
        if self.server:
            for kind in ("magnus_username", "magnus_password"):
                self.secret_store.clear(self.context, self._legacy_secret_kind(kind))
        self._clear_cached_cookie()

    def remove_profile_credentials(self, profile_id: str) -> None:
        try:
            safe_profile_id = validate_profile_id(profile_id)
        except ProfileError as error:
            raise MagnusError("invalid_profile") from error
        self._clear_profile_keys(safe_profile_id)
        if safe_profile_id == self.profile_id:
            self._clear_cached_cookie()

    def test_connection(self) -> None:
        """Authenticate without reading a Rock API entity."""

        with self.authenticated_cookie():
            return

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

    @contextmanager
    def authenticated_cookie(self) -> Iterator[str]:
        """Yield a validated .ROCK cookie from a brief, memory-only cache."""

        now = time.monotonic()
        with self._cache_lock:
            cached_cookie = (
                self._cached_cookie
                if self._cached_cookie and now < self._cached_cookie_deadline
                else ""
            )
        if cached_cookie:
            self._store_cached_cookie(cached_cookie)
            yield cached_cookie
            return

        self._clear_cached_cookie()
        with self._session() as (_, cookie):
            self._store_cached_cookie(cookie)
            yield cookie

    def invalidate_authenticated_cookie(self) -> None:
        """Discard the reusable cookie after a failed authenticated request."""

        self._clear_cached_cookie()

    def _has_cached_cookie(self) -> bool:
        now = time.monotonic()
        with self._cache_lock:
            return bool(
                self._cached_cookie and now < self._cached_cookie_deadline
            )

    def _store_cached_cookie(self, cookie: str) -> None:
        with self._cache_lock:
            self._cache_generation += 1
            generation = self._cache_generation
            if self._cache_timer is not None:
                self._cache_timer.cancel()
            self._cached_cookie = cookie
            self._cached_cookie_deadline = (
                time.monotonic() + AUTH_COOKIE_IDLE_SECONDS
            )
            timer = threading.Timer(
                AUTH_COOKIE_IDLE_SECONDS,
                self._expire_cached_cookie,
                args=(generation,),
            )
            timer.daemon = True
            self._cache_timer = timer
            timer.start()

    def _expire_cached_cookie(self, generation: int) -> None:
        with self._cache_lock:
            if generation != self._cache_generation:
                return
            self._cached_cookie = ""
            self._cached_cookie_deadline = 0.0
            self._cache_timer = None

    def _clear_cached_cookie(self) -> None:
        with self._cache_lock:
            self._cache_generation += 1
            if self._cache_timer is not None:
                self._cache_timer.cancel()
            self._cache_timer = None
            self._cached_cookie = ""
            self._cached_cookie_deadline = 0.0

    def _credentials(self) -> tuple[str, str] | None:
        if not self.server:
            return None
        username = self.secret_store.lookup(
            self.context, self._secret_kind("magnus_username")
        )
        password = self.secret_store.lookup(
            self.context, self._secret_kind("magnus_password")
        )
        return (username, password) if username and password else None

    def _secret_kind(self, kind: str) -> str:
        if self.profile_id:
            return f"{kind}:profile:{self.profile_id}"
        return self._legacy_secret_kind(kind)

    def _legacy_secret_kind(self, kind: str) -> str:
        origin_key = hashlib.sha256(self.server.encode()).hexdigest()[:16]
        return f"{kind}:{origin_key}"

    def _clear_profile_keys(self, profile_id: str) -> None:
        for kind in ("magnus_username", "magnus_password"):
            self.secret_store.clear(self.context, f"{kind}:profile:{profile_id}")

    def _run(self, command: list[str], maximum_bytes: int) -> bytes:
        with self._session() as (environment, _):
            config_home = Path(environment["XDG_CONFIG_HOME"])
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

    @contextmanager
    def _session(self) -> Iterator[tuple[dict[str, str], str]]:
        if not self.server:
            raise MagnusError("magnus_server_not_configured")
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

            if self._interactive_login(environment, username, password) != 0:
                raise MagnusError("magnus_login_failed")
            self._harden_temporary_files(config_home)
            yield environment, self._read_cookie(config_home)

    def _interactive_login(
        self, environment: dict[str, str], username: str, password: str
    ) -> int:
        """Drive Magnus 0.1.0's character-oriented password prompt safely."""

        process: subprocess.Popen[bytes] | None = None
        try:
            process = subprocess.Popen(
                [
                    self.executable,
                    "login",
                    self.server,
                    "--username",
                    username,
                    "--default",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=environment,
                bufsize=0,
            )
            if process.stdin is None or process.stdout is None:
                raise MagnusError("magnus_login_failed")

            prompt = b""
            deadline = time.monotonic() + PASSWORD_PROMPT_TIMEOUT_SECONDS
            while b"Password:" not in prompt:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise MagnusError("magnus_login_failed")
                readable, _, _ = select.select(
                    [process.stdout], [], [], min(remaining, 0.25)
                )
                if not readable:
                    if process.poll() is not None:
                        raise MagnusError("magnus_login_failed")
                    continue
                chunk = os.read(process.stdout.fileno(), 256)
                if not chunk:
                    raise MagnusError("magnus_login_failed")
                prompt = (prompt + chunk)[-4_096:]

            for character in password:
                process.stdin.write(character.encode("utf-8"))
                process.stdin.flush()
                time.sleep(PASSWORD_KEYSTROKE_DELAY_SECONDS)
            process.stdin.write(b"\n")
            process.stdin.flush()
            process.stdin.close()
            return process.wait(timeout=20)
        except (BrokenPipeError, OSError, subprocess.TimeoutExpired) as error:
            raise MagnusError("magnus_login_failed") from error
        finally:
            if process is not None:
                if process.poll() is None:
                    process.kill()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        pass
                for stream in (process.stdin, process.stdout):
                    if stream is not None and not stream.closed:
                        stream.close()

    def _read_cookie(self, config_home: Path) -> str:
        path = config_home / "magnus-cli-cookies-nodejs" / "config.json"
        try:
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(config_home.resolve()):
                raise MagnusError("invalid_magnus_cookie")
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(path, flags)
            try:
                info = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_size > MAX_COOKIE_CONFIG_BYTES
                ):
                    raise MagnusError("invalid_magnus_cookie")
                raw = os.read(descriptor, MAX_COOKIE_CONFIG_BYTES + 1)
            finally:
                os.close(descriptor)
            if len(raw) > MAX_COOKIE_CONFIG_BYTES:
                raise MagnusError("invalid_magnus_cookie")
            value = json.loads(raw)
            records = self._matching_cookie_records(value)
            if len(records) != 1:
                raise MagnusError("invalid_magnus_cookie")
            cookie = records[0].get("cookie")
        except MagnusError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise MagnusError("invalid_magnus_cookie") from error

        if (
            not isinstance(cookie, str)
            or not cookie.startswith(".ROCK=")
            or len(cookie) < 7
            or len(cookie) > 16 * 1024
            or any(ord(char) < 33 or char in ';,\\"' for char in cookie)
        ):
            raise MagnusError("invalid_magnus_cookie")
        return cookie

    def _matching_cookie_records(self, value: Any) -> list[dict[str, Any]]:
        """Find Conf records without relying on its dot-notation JSON layout."""

        matches: list[dict[str, Any]] = []
        pending: list[tuple[Any, int]] = [(value, 0)]
        visited = 0
        while pending:
            current, depth = pending.pop()
            visited += 1
            if visited > MAX_COOKIE_CONFIG_NODES or depth > MAX_COOKIE_CONFIG_DEPTH:
                raise MagnusError("invalid_magnus_cookie")
            if not isinstance(current, dict):
                continue
            if current.get("serverUrl") == self.server and "cookie" in current:
                matches.append(current)
                if len(matches) > 1:
                    raise MagnusError("invalid_magnus_cookie")
            pending.extend((child, depth + 1) for child in current.values())
        return matches

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

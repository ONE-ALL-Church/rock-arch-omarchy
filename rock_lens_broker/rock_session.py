from __future__ import annotations

import hashlib
import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol

from .auth import SecretStore, SecretToolStore
from .contracts import Context
from .origin import OriginError, validate_rock_origin
from .profiles import ProfileError, validate_profile_id

AUTH_COOKIE_IDLE_SECONDS = 15 * 60
HTTP_TIMEOUT_SECONDS = 15
MAX_PASSWORD_BYTES = 1_024
MAX_COOKIE_BYTES = 16 * 1024
ROCK_LENS_USER_AGENT = "Rock-Lens/0.10"


class RockSessionError(Exception):
    """A stable login failure that never includes private response details."""


class LoginClient(Protocol):
    def login(self, origin: str, username: str, password: str) -> str: ...


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def validate_rock_cookie(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith(".ROCK=")
        or len(value) < 7
        or len(value) > MAX_COOKIE_BYTES
        or any(ord(char) < 33 or char in ';,\\"' for char in value)
    ):
        raise RockSessionError("invalid_rock_cookie")
    return value


class RockSessionHttpClient:
    """Fixed-origin Rock username/password login with redirects disabled."""

    def __init__(self, opener: Any | None = None) -> None:
        self._opener = opener

    def login(self, origin: str, username: str, password: str) -> str:
        try:
            safe_origin = validate_rock_origin(origin)
        except OriginError as error:
            raise RockSessionError("invalid_rock_origin") from error
        request = urllib.request.Request(
            safe_origin + "/api/Auth/Login",
            data=json.dumps(
                {"username": username, "password": password},
                separators=(",", ":"),
            ).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": ROCK_LENS_USER_AGENT,
            },
            method="POST",
        )
        try:
            opener = self._opener or urllib.request.build_opener(_RejectRedirects())
            with opener.open(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                status = getattr(response, "status", None) or response.getcode()
                if status not in (200, 204):
                    raise RockSessionError("rock_login_failed")
                cookie = self._cookie_from_headers(response.headers)
        except RockSessionError:
            raise
        except (OSError, urllib.error.HTTPError, urllib.error.URLError) as error:
            raise RockSessionError("rock_login_failed") from error
        return validate_rock_cookie(cookie)

    @staticmethod
    def _cookie_from_headers(headers: Any) -> str:
        values: list[str] = []
        getter = getattr(headers, "get_all", None)
        if callable(getter):
            values = [str(value) for value in (getter("Set-Cookie") or [])]
        if not values:
            value = headers.get("Set-Cookie") if hasattr(headers, "get") else None
            if value:
                values = [str(value)]
        for header in values:
            for component in header.split(";"):
                candidate = component.strip()
                if candidate.startswith(".ROCK="):
                    return candidate
        raise RockSessionError("invalid_rock_cookie")


class RockSessionProvider:
    """Per-profile Rock login backed by Secret Service and an in-memory cookie."""

    def __init__(
        self,
        origin: str | None = None,
        profile_id: str | None = None,
        secret_store: SecretStore | None = None,
        http: LoginClient | None = None,
        context: Context = Context.PROD,
    ) -> None:
        self.origin = validate_rock_origin(origin) if origin else ""
        try:
            self.profile_id = validate_profile_id(profile_id) if profile_id else ""
        except ProfileError as error:
            raise RockSessionError("invalid_profile") from error
        self.secret_store = secret_store or SecretToolStore()
        self.http = http or RockSessionHttpClient()
        self.context = context
        self._cached_cookie = ""
        self._cached_cookie_deadline = 0.0
        self._cache_generation = 0
        self._cache_lock = threading.Lock()
        self._cache_timer: threading.Timer | None = None

    def status(self) -> dict[str, Any]:
        storage_available = self.secret_store.available()
        configured = (
            storage_available
            and bool(self.origin)
            and (self._has_cached_cookie() or bool(self._credentials()))
        )
        state = "connected" if self._has_cached_cookie() else (
            "ready" if configured else "signed_out"
        )
        return {
            "available": storage_available,
            "configured": configured,
            "state": state,
            "server": self.origin.removeprefix("https://"),
        }

    def set_server(self, value: str) -> None:
        try:
            origin = validate_rock_origin(value)
        except OriginError as error:
            raise RockSessionError("invalid_rock_origin") from error
        if origin != self.origin:
            self._clear_cached_cookie()
        self.origin = origin

    def set_profile(self, profile_id: str, origin: str) -> None:
        try:
            safe_profile_id = validate_profile_id(profile_id)
            safe_origin = validate_rock_origin(origin)
        except (ProfileError, OriginError) as error:
            raise RockSessionError("invalid_profile") from error
        if safe_profile_id != self.profile_id or safe_origin != self.origin:
            self._clear_cached_cookie()
        self.profile_id = safe_profile_id
        self.origin = safe_origin
        self.migrate_legacy_credentials()

    def clear_profile(self) -> None:
        self._clear_cached_cookie()
        self.profile_id = ""
        self.origin = ""

    def configure(self, username: str, password: str) -> None:
        if not self.origin or not self.profile_id:
            raise RockSessionError("rock_profile_not_configured")
        safe_username, safe_password = self._validate_credentials(username, password)
        if not self.secret_store.available():
            raise RockSessionError("secure_storage_unavailable")

        # Verify first so a typo never replaces a working saved login.
        cookie = self.http.login(self.origin, safe_username, safe_password)
        old_username = self.secret_store.lookup(
            self.context, self._secret_kind("rock_username")
        )
        old_password = self.secret_store.lookup(
            self.context, self._secret_kind("rock_password")
        )
        try:
            self.secret_store.store(
                self.context, self._secret_kind("rock_username"), safe_username
            )
            self.secret_store.store(
                self.context, self._secret_kind("rock_password"), safe_password
            )
        except Exception as error:
            self._restore_secret("rock_username", old_username)
            self._restore_secret("rock_password", old_password)
            self._clear_cached_cookie()
            raise RockSessionError("secure_storage_failed") from error
        self._clear_legacy_keys()
        self._store_cached_cookie(cookie)

    def migrate_legacy_credentials(self) -> bool:
        """Move profile-scoped credentials written by the old Magnus adapter."""

        if not self.profile_id or not self.origin or not self.secret_store.available():
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
            # The earliest build keyed credentials by the origin instead of profile.
            username = self.secret_store.lookup(
                self.context, self._origin_secret_kind("magnus_username")
            )
            password = self.secret_store.lookup(
                self.context, self._origin_secret_kind("magnus_password")
            )
        if not username or not password:
            return False
        safe_username, safe_password = self._validate_credentials(username, password)
        try:
            self.secret_store.store(
                self.context, self._secret_kind("rock_username"), safe_username
            )
            self.secret_store.store(
                self.context, self._secret_kind("rock_password"), safe_password
            )
        except Exception as error:
            self._clear_current_keys()
            raise RockSessionError("secure_storage_failed") from error
        if self._credentials() != (safe_username, safe_password):
            self._clear_current_keys()
            raise RockSessionError("secure_storage_failed")
        self._clear_legacy_keys()
        return True

    def sign_out(self) -> None:
        self._clear_current_keys()
        self._clear_legacy_keys()
        self._clear_cached_cookie()

    def remove_profile_credentials(self, profile_id: str) -> None:
        try:
            safe_profile_id = validate_profile_id(profile_id)
        except ProfileError as error:
            raise RockSessionError("invalid_profile") from error
        for kind in (
            "rock_username",
            "rock_password",
            "magnus_username",
            "magnus_password",
        ):
            self.secret_store.clear(
                self.context, f"{kind}:profile:{safe_profile_id}"
            )
        if safe_profile_id == self.profile_id:
            self._clear_cached_cookie()

    def test_connection(self) -> None:
        self._clear_cached_cookie()
        with self.authenticated_cookie():
            return

    @contextmanager
    def authenticated_cookie(self) -> Iterator[str]:
        now = time.monotonic()
        with self._cache_lock:
            cookie = (
                self._cached_cookie
                if self._cached_cookie and now < self._cached_cookie_deadline
                else ""
            )
        if not cookie:
            self._clear_cached_cookie()
            credentials = self._credentials()
            if not self.origin or not credentials:
                raise RockSessionError("rock_login_required")
            cookie = self.http.login(self.origin, *credentials)
        self._store_cached_cookie(cookie)
        yield cookie

    def invalidate_authenticated_cookie(self) -> None:
        self._clear_cached_cookie()

    def _credentials(self) -> tuple[str, str] | None:
        if not self.profile_id:
            return None
        username = self.secret_store.lookup(
            self.context, self._secret_kind("rock_username")
        )
        password = self.secret_store.lookup(
            self.context, self._secret_kind("rock_password")
        )
        return (username, password) if username and password else None

    @staticmethod
    def _validate_credentials(username: str, password: str) -> tuple[str, str]:
        safe_username = username.strip()
        if (
            not safe_username
            or len(safe_username) > 200
            or any(ord(char) < 32 for char in safe_username)
        ):
            raise RockSessionError("invalid_rock_username")
        if (
            not password
            or len(password.encode("utf-8")) > MAX_PASSWORD_BYTES
            or any(char in password for char in "\x00\r\n")
        ):
            raise RockSessionError("invalid_rock_password")
        return safe_username, password

    def _secret_kind(self, kind: str) -> str:
        return f"{kind}:profile:{self.profile_id}"

    def _legacy_secret_kind(self, kind: str) -> str:
        return f"{kind}:profile:{self.profile_id}"

    def _origin_secret_kind(self, kind: str) -> str:
        origin_key = hashlib.sha256(self.origin.encode()).hexdigest()[:16]
        return f"{kind}:{origin_key}"

    def _clear_current_keys(self) -> None:
        if not self.profile_id:
            return
        for kind in ("rock_username", "rock_password"):
            self.secret_store.clear(self.context, self._secret_kind(kind))

    def _clear_legacy_keys(self) -> None:
        if not self.profile_id:
            return
        for kind in ("magnus_username", "magnus_password"):
            self.secret_store.clear(self.context, self._legacy_secret_kind(kind))
            if self.origin:
                self.secret_store.clear(self.context, self._origin_secret_kind(kind))

    def _restore_secret(self, kind: str, value: str | None) -> None:
        if value is None:
            self.secret_store.clear(self.context, self._secret_kind(kind))
        else:
            self.secret_store.store(self.context, self._secret_kind(kind), value)

    def _has_cached_cookie(self) -> bool:
        now = time.monotonic()
        with self._cache_lock:
            return bool(self._cached_cookie and now < self._cached_cookie_deadline)

    def _store_cached_cookie(self, cookie: str) -> None:
        safe_cookie = validate_rock_cookie(cookie)
        with self._cache_lock:
            self._cache_generation += 1
            generation = self._cache_generation
            if self._cache_timer is not None:
                self._cache_timer.cancel()
            self._cached_cookie = safe_cookie
            self._cached_cookie_deadline = time.monotonic() + AUTH_COOKIE_IDLE_SECONDS
            timer = threading.Timer(
                AUTH_COOKIE_IDLE_SECONDS, self._expire_cached_cookie, args=(generation,)
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

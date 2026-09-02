from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import shutil
import stat
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Protocol

from .contracts import Context

LOGIN_TIMEOUT_SECONDS = 180
HTTP_TIMEOUT_SECONDS = 10
TOKEN_EXPIRY_LEEWAY_SECONDS = 60
DEFAULT_REDIRECT_URI = "http://127.0.0.1:41397/oauth/callback"
DEFAULT_SCOPES = ("openid", "offline_access")


class AuthState(StrEnum):
    UNCONFIGURED = "unconfigured"
    SIGNED_OUT = "signed_out"
    STARTING = "starting"
    WAITING = "waiting"
    REFRESHING = "refreshing"
    AUTHENTICATED = "authenticated"
    EXPIRED = "expired"
    FAILED = "failed"


AUTH_LABELS = {
    AuthState.UNCONFIGURED: "OAuth setup needed",
    AuthState.SIGNED_OUT: "Signed out",
    AuthState.STARTING: "Starting secure sign-in…",
    AuthState.WAITING: "Finish sign-in in your browser",
    AuthState.REFRESHING: "Renewing Rock session…",
    AuthState.AUTHENTICATED: "Signed in with Rock",
    AuthState.EXPIRED: "Rock session expired",
    AuthState.FAILED: "Rock sign-in failed",
}


class OAuthError(Exception):
    """A private failure whose details must never cross the broker boundary."""


@dataclass(frozen=True)
class OidcConfig:
    issuer: str
    client_id: str
    redirect_uri: str
    scopes: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> OidcConfig:
        issuer = _validate_issuer(value.get("issuer"))
        client_id = str(value.get("client_id") or "").strip()
        if (
            not client_id
            or len(client_id) > 300
            or any(char.isspace() for char in client_id)
        ):
            raise ValueError("invalid client id")

        redirect_uri = _validate_redirect_uri(value.get("redirect_uri"))
        raw_scopes = value.get("scopes", DEFAULT_SCOPES)
        if not isinstance(raw_scopes, (list, tuple)):
            raise TypeError("invalid scopes")
        scopes = tuple(
            dict.fromkeys(
                str(scope).strip() for scope in raw_scopes if str(scope).strip()
            )
        )
        if "openid" not in scopes or len(scopes) > 20:
            raise ValueError("openid scope is required")
        if any(
            len(scope) > 120 or any(char.isspace() for char in scope)
            for scope in scopes
        ):
            raise ValueError("invalid scopes")

        return cls(
            issuer=issuer, client_id=client_id, redirect_uri=redirect_uri, scopes=scopes
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "issuer": self.issuer,
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scopes": list(self.scopes),
        }


@dataclass(frozen=True)
class DiscoveryDocument:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    refresh_token: str | None
    token_type: str
    expires_at: int
    scope: str

    @classmethod
    def from_response(
        cls,
        value: dict[str, Any],
        now: float,
        previous_refresh_token: str | None = None,
    ) -> TokenSet:
        access_token = str(value.get("access_token") or "")
        token_type = str(value.get("token_type") or "")
        if (
            not access_token
            or len(access_token) > 64 * 1024
            or token_type.lower() != "bearer"
        ):
            raise OAuthError("invalid token response")
        expires_value = value.get("expires_in")
        if not isinstance(expires_value, (int, str)) or isinstance(expires_value, bool):
            raise OAuthError("invalid token lifetime")
        try:
            expires_in = int(expires_value)
        except (TypeError, ValueError) as error:
            raise OAuthError("invalid token lifetime") from error
        if expires_in < 1 or expires_in > 31 * 24 * 60 * 60:
            raise OAuthError("invalid token lifetime")

        refresh_value = value.get("refresh_token")
        refresh_token = str(refresh_value) if refresh_value else previous_refresh_token
        if refresh_token and len(refresh_token) > 64 * 1024:
            raise OAuthError("invalid refresh token")

        return cls(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_at=int(now) + expires_in,
            scope=str(value.get("scope") or "")[:2_000],
        )

    @classmethod
    def from_json(cls, value: str) -> TokenSet:
        raw = json.loads(value)
        if not isinstance(raw, dict):
            raise TypeError("invalid token record")
        token = cls(
            access_token=str(raw["access_token"]),
            refresh_token=str(raw["refresh_token"])
            if raw.get("refresh_token")
            else None,
            token_type=str(raw["token_type"]),
            expires_at=int(raw["expires_at"]),
            scope=str(raw.get("scope") or ""),
        )
        if (
            not token.access_token
            or len(token.access_token) > 64 * 1024
            or (token.refresh_token and len(token.refresh_token) > 64 * 1024)
            or token.token_type.lower() != "bearer"
            or len(token.scope) > 2_000
        ):
            raise ValueError("invalid token record")
        return token

    def to_json(self) -> str:
        return json.dumps(
            {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "token_type": self.token_type,
                "expires_at": self.expires_at,
                "scope": self.scope,
            },
            separators=(",", ":"),
        )

    def is_valid(self, now: float) -> bool:
        return (
            self.token_type.lower() == "bearer"
            and self.expires_at > int(now) + TOKEN_EXPIRY_LEEWAY_SECONDS
        )


class ConfigStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def get(self, context: Context) -> OidcConfig | None:
        try:
            metadata = self.path.stat()
            if (
                metadata.st_uid != os.getuid()
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_mode & 0o077
            ):
                return None
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            contexts = raw.get("contexts") if isinstance(raw, dict) else None
            value = contexts.get(context.value) if isinstance(contexts, dict) else None
            return OidcConfig.from_dict(value) if isinstance(value, dict) else None
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None

    def set(self, context: Context, config: OidcConfig) -> None:
        raw: dict[str, Any] = {"contexts": {}}
        try:
            current = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(current, dict) and isinstance(current.get("contexts"), dict):
                raw = current
        except (OSError, json.JSONDecodeError):
            pass

        raw["contexts"][context.value] = config.to_dict()
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path.parent.chmod(0o700)
        temporary = self.path.with_name(self.path.name + ".tmp")
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(raw, indent=2, sort_keys=True) + "\n")
        temporary.replace(self.path)
        self.path.chmod(0o600)


class SecretStore(Protocol):
    def available(self) -> bool: ...

    def lookup(self, context: Context, kind: str) -> str | None: ...

    def store(self, context: Context, kind: str, value: str) -> None: ...

    def clear(self, context: Context, kind: str) -> None: ...


class HttpClient(Protocol):
    def get_json(self, url: str) -> dict[str, Any]: ...

    def post_form(self, url: str, fields: dict[str, str]) -> dict[str, Any]: ...


class SecretToolStore:
    """Secret Service storage that never puts secret values in argv or logs."""

    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or shutil.which("secret-tool") or ""

    def available(self) -> bool:
        return bool(self.executable)

    def _attributes(self, context: Context, kind: str) -> list[str]:
        return ["application", "rock-lens", "context", context.value, "kind", kind]

    def lookup(self, context: Context, kind: str) -> str | None:
        if not self.available():
            return None
        try:
            result = subprocess.run(
                [self.executable, "lookup", *self._attributes(context, kind)],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=HTTP_TIMEOUT_SECONDS,
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
            raise OAuthError("secure storage unavailable")
        try:
            result = subprocess.run(
                [
                    self.executable,
                    "store",
                    f"--label=Rock Lens {context.value} {kind}",
                    *self._attributes(context, kind),
                ],
                input=value.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=HTTP_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise OAuthError("secure storage failed") from error
        if result.returncode != 0:
            raise OAuthError("secure storage failed")

    def clear(self, context: Context, kind: str) -> None:
        if not self.available():
            return
        try:
            subprocess.run(
                [self.executable, "clear", *self._attributes(context, kind)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=HTTP_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass


class JsonHttpClient:
    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(_RejectRedirects)

    def get_json(self, url: str) -> dict[str, Any]:
        _validate_transport_url(url)
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        return self._request(request)

    def post_form(self, url: str, fields: dict[str, str]) -> dict[str, Any]:
        _validate_transport_url(url)
        request = urllib.request.Request(
            url,
            data=urllib.parse.urlencode(fields).encode("ascii"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        return self._request(request)

    def _request(self, request: urllib.request.Request) -> dict[str, Any]:
        try:
            with self._opener.open(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                if response.status != 200:
                    raise OAuthError("unexpected http status")
                body = response.read(256 * 1024 + 1)
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as error:
            raise OAuthError("oauth request failed") from error
        if len(body) > 256 * 1024:
            raise OAuthError("oauth response too large")
        try:
            value = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OAuthError("invalid oauth response") from error
        if not isinstance(value, dict):
            raise OAuthError("invalid oauth response")
        return value


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


@dataclass
class _ContextRuntime:
    state: AuthState = AuthState.SIGNED_OUT
    error: str | None = None
    worker: threading.Thread | None = None


class OAuthManager:
    def __init__(
        self,
        config_store: ConfigStore,
        secret_store: SecretStore | None = None,
        http: HttpClient | None = None,
        browser_open: Callable[[str], bool] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.config_store = config_store
        self.secret_store = secret_store or SecretToolStore()
        self.http = http or JsonHttpClient()
        self.browser_open = browser_open or (
            lambda url: bool(webbrowser.open(url, new=1, autoraise=True))
        )
        self.clock = clock or time.time
        self._lock = threading.Lock()
        self._runtime = {context: _ContextRuntime() for context in Context}

    def public_status(
        self, context: Context, allow_refresh: bool = True
    ) -> dict[str, Any]:
        config = self.config_store.get(context)
        if not config:
            return self._public(AuthState.UNCONFIGURED, configured=False)

        with self._lock:
            runtime = self._runtime[context]
            if runtime.state in {
                AuthState.STARTING,
                AuthState.WAITING,
                AuthState.REFRESHING,
                AuthState.FAILED,
            } or (runtime.state is AuthState.EXPIRED and runtime.error):
                return self._public(runtime.state, configured=True, error=runtime.error)

        token = self._load_token(context)
        if token and token.is_valid(self.clock()):
            self._set_state(context, AuthState.AUTHENTICATED)
            return self._public(AuthState.AUTHENTICATED, configured=True)
        if token and token.refresh_token and allow_refresh:
            self._start_worker(context, AuthState.REFRESHING, self._refresh_worker)
            return self._public(AuthState.REFRESHING, configured=True)
        state = AuthState.EXPIRED if token else AuthState.SIGNED_OUT
        self._set_state(context, state)
        return self._public(state, configured=True)

    def begin_login(self, context: Context) -> dict[str, Any]:
        if not self.config_store.get(context):
            return self._public(AuthState.UNCONFIGURED, configured=False)
        if not self.secret_store.available():
            self._set_state(context, AuthState.FAILED, "secure_storage_unavailable")
            return self._public(
                AuthState.FAILED, configured=True, error="secure_storage_unavailable"
            )
        if not self._start_worker(context, AuthState.STARTING, self._login_worker):
            return self.public_status(context, allow_refresh=False)
        return self._public(AuthState.STARTING, configured=True)

    def disconnect(self, context: Context) -> dict[str, Any]:
        self.secret_store.clear(context, "tokens")
        self._set_state(context, AuthState.SIGNED_OUT)
        return self._public(
            AuthState.SIGNED_OUT, configured=self.config_store.get(context) is not None
        )

    def access_token(self, context: Context) -> str | None:
        """Return a valid token only to an in-process adapter; never serialize it."""
        token = self._load_token(context)
        return token.access_token if token and token.is_valid(self.clock()) else None

    def _start_worker(
        self,
        context: Context,
        state: AuthState,
        target: Callable[[Context], None],
    ) -> bool:
        with self._lock:
            runtime = self._runtime[context]
            if runtime.worker and runtime.worker.is_alive():
                return False
            runtime.state = state
            runtime.error = None
            worker = threading.Thread(
                target=target,
                args=(context,),
                name=f"rock-lens-{state.value.lower()}",
                daemon=True,
            )
            runtime.worker = worker
            worker.start()
            return True

    def _login_worker(self, context: Context) -> None:
        server: HTTPServer | None = None
        try:
            config = self.config_store.get(context)
            if not config:
                self._set_state(context, AuthState.UNCONFIGURED)
                return
            discovery = self._discover(config)
            verifier = _random_urlsafe(64)
            challenge = _base64url(hashlib.sha256(verifier.encode("ascii")).digest())
            state = _random_urlsafe(32)
            nonce = _random_urlsafe(32)
            redirect = urllib.parse.urlsplit(config.redirect_uri)
            host = redirect.hostname or ""
            server = _OAuthCallbackServer(
                (host, redirect.port or 0), redirect.path, state
            )
            server.timeout = 0.5

            auth_url = build_authorization_url(
                config, discovery, state, nonce, challenge
            )
            self._set_state(context, AuthState.WAITING)
            if not self.browser_open(auth_url):
                raise OAuthError("browser launch failed")

            deadline = self.clock() + LOGIN_TIMEOUT_SECONDS
            while self.clock() < deadline and server.result is None:
                server.handle_request()
            if server.result is None:
                raise OAuthError("login timed out")
            if server.result.get("error"):
                error_code = (
                    "login_denied"
                    if server.result.get("error") == "access_denied"
                    else "login_failed"
                )
                self._set_state(context, AuthState.FAILED, error_code)
                return
            code = server.result.get("code")
            if not code:
                raise OAuthError("authorization code missing")

            fields = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config.redirect_uri,
                "client_id": config.client_id,
                "code_verifier": verifier,
            }
            client_secret = self.secret_store.lookup(context, "client_secret")
            if client_secret:
                fields["client_secret"] = client_secret
            token_response = self.http.post_form(discovery.token_endpoint, fields)
            token = TokenSet.from_response(token_response, self.clock())
            self.secret_store.store(context, "tokens", token.to_json())
            self._set_state(context, AuthState.AUTHENTICATED)
        except (OAuthError, OSError, ValueError, TypeError):
            self._set_state(context, AuthState.FAILED, "login_failed")
        finally:
            if server:
                server.server_close()
            self._clear_worker(context)

    def _refresh_worker(self, context: Context) -> None:
        try:
            config = self.config_store.get(context)
            token = self._load_token(context)
            if not config or not token or not token.refresh_token:
                self._set_state(context, AuthState.EXPIRED)
                return
            discovery = self._discover(config)
            fields = {
                "grant_type": "refresh_token",
                "refresh_token": token.refresh_token,
                "client_id": config.client_id,
            }
            client_secret = self.secret_store.lookup(context, "client_secret")
            if client_secret:
                fields["client_secret"] = client_secret
            response = self.http.post_form(discovery.token_endpoint, fields)
            refreshed = TokenSet.from_response(
                response, self.clock(), token.refresh_token
            )
            self.secret_store.store(context, "tokens", refreshed.to_json())
            self._set_state(context, AuthState.AUTHENTICATED)
        except (OAuthError, OSError, ValueError, TypeError):
            self.secret_store.clear(context, "tokens")
            self._set_state(context, AuthState.EXPIRED, "refresh_failed")
        finally:
            self._clear_worker(context)

    def _discover(self, config: OidcConfig) -> DiscoveryDocument:
        url = urllib.parse.urljoin(config.issuer, ".well-known/openid-configuration")
        value = self.http.get_json(url)
        issuer = _validate_issuer(value.get("issuer"))
        if issuer.rstrip("/") != config.issuer.rstrip("/"):
            raise OAuthError("issuer mismatch")
        authorization_endpoint = _validate_same_origin_https(
            value.get("authorization_endpoint"), config.issuer
        )
        token_endpoint = _validate_same_origin_https(
            value.get("token_endpoint"), config.issuer
        )
        return DiscoveryDocument(
            issuer=issuer,
            authorization_endpoint=authorization_endpoint,
            token_endpoint=token_endpoint,
        )

    def _load_token(self, context: Context) -> TokenSet | None:
        value = self.secret_store.lookup(context, "tokens")
        if not value:
            return None
        try:
            return TokenSet.from_json(value)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            self.secret_store.clear(context, "tokens")
            return None

    def _set_state(
        self, context: Context, state: AuthState, error: str | None = None
    ) -> None:
        with self._lock:
            runtime = self._runtime[context]
            runtime.state = state
            runtime.error = error

    def _clear_worker(self, context: Context) -> None:
        with self._lock:
            self._runtime[context].worker = None

    @staticmethod
    def _public(
        state: AuthState, configured: bool, error: str | None = None
    ) -> dict[str, Any]:
        response: dict[str, Any] = {
            "state": state.value,
            "configured": configured,
            "label": AUTH_LABELS[state],
        }
        if error:
            response["error"] = error
        return response


class _OAuthCallbackServer(HTTPServer):
    allow_reuse_address = False

    def __init__(
        self, address: tuple[str, int], expected_path: str, expected_state: str
    ) -> None:
        self.expected_path = expected_path
        self.expected_state = expected_state
        self.result: dict[str, str] | None = None
        super().__init__(address, _OAuthCallbackHandler)

    def handle_error(self, request: Any, client_address: Any) -> None:
        return


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    server: _OAuthCallbackServer

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path != self.server.expected_path or len(parsed.query) > 8_192:
            self.send_error(404)
            return
        try:
            query = urllib.parse.parse_qs(
                parsed.query, keep_blank_values=True, max_num_fields=12
            )
        except ValueError:
            self._respond(
                400,
                "Rock Lens did not receive a valid sign-in response. You can close this tab.",
            )
            return
        states = query.get("state", [])
        codes = query.get("code", [])
        errors = query.get("error", [])
        if len(states) != 1 or not secrets.compare_digest(
            states[0], self.server.expected_state
        ):
            self._respond(
                400, "Rock Lens could not verify this sign-in. You can close this tab."
            )
            return
        if len(errors) == 1:
            self.server.result = {"error": errors[0][:80]}
            self._respond(200, "Rock sign-in was cancelled. You can close this tab.")
            return
        if len(codes) != 1 or not codes[0] or len(codes[0]) > 8_192:
            self._respond(
                400,
                "Rock Lens did not receive a valid sign-in response. You can close this tab.",
            )
            return
        self.server.result = {"code": codes[0]}
        self._respond(200, "Rock Lens is signed in. You can close this tab.")

    def _respond(self, status: int, message: str) -> None:
        body = (
            "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
            "<title>Rock Lens</title><style>body{font:18px system-ui;margin:4rem;max-width:40rem}</style>"
            f"<p>{message}</p>"
        ).encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'"
        )
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def build_authorization_url(
    config: OidcConfig,
    discovery: DiscoveryDocument,
    state: str,
    nonce: str,
    code_challenge: str,
) -> str:
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "scope": " ".join(config.scopes),
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    separator = (
        "&" if urllib.parse.urlsplit(discovery.authorization_endpoint).query else "?"
    )
    return discovery.authorization_endpoint + separator + query


def default_config_path() -> Path:
    return (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "rock-lens"
        / "oidc.json"
    )


def _validate_issuer(value: Any) -> str:
    issuer = str(value or "").strip()
    parsed = urllib.parse.urlsplit(issuer)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("invalid issuer")
    return issuer.rstrip("/") + "/"


def _validate_redirect_uri(value: Any) -> str:
    redirect_uri = str(value or "").strip()
    parsed = urllib.parse.urlsplit(redirect_uri)
    if (
        parsed.scheme.lower() != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.port is None
        or parsed.port < 1024
        or not parsed.path.startswith("/")
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("redirect uri must be an unprivileged loopback HTTP address")
    return redirect_uri


def _validate_same_origin_https(value: Any, issuer: str) -> str:
    endpoint = str(value or "").strip()
    parsed = urllib.parse.urlsplit(endpoint)
    issuer_parsed = urllib.parse.urlsplit(issuer)
    issuer_hostname = issuer_parsed.hostname
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or not issuer_hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
        or (parsed.scheme.lower(), parsed.hostname.lower(), parsed.port)
        != (
            issuer_parsed.scheme.lower(),
            issuer_hostname.lower(),
            issuer_parsed.port,
        )
    ):
        raise OAuthError("invalid oauth endpoint")
    return endpoint


def _validate_transport_url(value: str) -> None:
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise OAuthError("invalid oauth transport url")


def _random_urlsafe(bytes_count: int) -> str:
    return secrets.token_urlsafe(bytes_count)


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

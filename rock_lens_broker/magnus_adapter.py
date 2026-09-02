from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from contextlib import AbstractContextManager
from pathlib import PurePosixPath
from typing import Any, Protocol

from .contracts import sanitize_text
from .origin import DEFAULT_ROCK_ORIGIN, OriginError, validate_rock_origin
from .rock_session import RockSessionError

CANONICAL_MAGNUS_SERVER = DEFAULT_ROCK_ORIGIN
DEFAULT_TREE_PATH = "api/TriumphTech/Magnus/GetTreeItems/root"
TREE_PATH_PREFIX = "api/TriumphTech/Magnus/GetTreeItems/"
FILE_PATH_PREFIX = "/FileContent/"
MAGNUS_API_PREFIX = "/api/TriumphTech/Magnus"
MAX_TREE_ITEMS = 500
MAX_TREE_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_PREVIEW_BYTES = 64 * 1024
MAX_REGISTERED_ITEMS = 2_000
HTTP_TIMEOUT_SECONDS = 20
ROCK_LENS_USER_AGENT = "Rock-Lens/0.10"


class MagnusError(Exception):
    """A stable Magnus failure that never includes URLs or response bodies."""


class MagnusUnavailableError(MagnusError):
    """The selected Rock instance or account cannot use Magnus."""


class CookieProvider(Protocol):
    def status(self) -> dict[str, Any]: ...

    def authenticated_cookie(self) -> AbstractContextManager[str]: ...

    def invalidate_authenticated_cookie(self) -> None: ...


class MagnusHttp(Protocol):
    def get_json(self, origin: str, path: str, cookie: str) -> Any: ...

    def get_bytes(self, origin: str, path: str, cookie: str) -> bytes: ...


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


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
    if path.startswith(MAGNUS_API_PREFIX + FILE_PATH_PREFIX):
        path = path.removeprefix(MAGNUS_API_PREFIX)
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


class MagnusHttpClient:
    """Same-origin, redirect-free GET client for the bounded Magnus surface."""

    def __init__(self, opener: Any | None = None) -> None:
        self._opener = opener

    def get_json(self, origin: str, path: str, cookie: str) -> Any:
        raw = self._get(origin, path, cookie, MAX_TREE_OUTPUT_BYTES)
        try:
            return json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise MagnusError("invalid_magnus_response") from error

    def get_bytes(self, origin: str, path: str, cookie: str) -> bytes:
        return self._get(origin, path, cookie, MAX_FILE_BYTES)

    def _get(self, origin: str, path: str, cookie: str, maximum: int) -> bytes:
        safe_origin = validate_magnus_server(origin)
        if (
            not isinstance(path, str)
            or not path.startswith("/")
            or "://" in path
            or "?" in path
            or "#" in path
            or "\\" in path
            or any(ord(char) < 32 for char in path)
        ):
            raise MagnusError("invalid_magnus_path")
        if (
            not isinstance(cookie, str)
            or not cookie.startswith(".ROCK=")
            or len(cookie) > 16 * 1024
            or any(ord(char) < 33 or char in ';,\\"' for char in cookie)
        ):
            raise MagnusError("invalid_rock_cookie")
        request = urllib.request.Request(
            safe_origin + path,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Cookie": cookie,
                "User-Agent": ROCK_LENS_USER_AGENT,
            },
            method="GET",
        )
        try:
            opener = self._opener or urllib.request.build_opener(_RejectRedirects())
            with opener.open(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                raw = response.read(maximum + 1)
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
            if status in (401, 403, 404):
                raise MagnusUnavailableError("magnus_unavailable_for_user") from error
            raise MagnusError("magnus_request_failed") from error
        except (OSError, urllib.error.URLError) as error:
            raise MagnusError("magnus_request_failed") from error
        if len(raw) > maximum:
            raise MagnusError("magnus_response_out_of_bounds")
        return raw


class MagnusReadOnlyAdapter:
    """Optional native Magnus browse/read support using an existing Rock session."""

    def __init__(
        self,
        cookie_provider: CookieProvider,
        server: str | None = None,
        http: MagnusHttp | None = None,
    ) -> None:
        self.cookie_provider = cookie_provider
        self.server = validate_magnus_server(server) if server else ""
        self.profile_id = ""
        self.http = http or MagnusHttpClient()
        self._access = "unknown"
        self._key = secrets.token_bytes(32)
        self._targets: OrderedDict[str, tuple[str, str]] = OrderedDict()

    def status(self) -> dict[str, Any]:
        session_status = self.cookie_provider.status()
        configured = bool(session_status.get("configured")) and bool(self.server)
        return {
            "available": configured and self._access == "available",
            "configured": configured,
            "state": self._access if configured else "signed_out",
            "mode": "read_only",
            "capabilities": (
                ["browse", "preview", "hash"]
                if configured and self._access == "available"
                else []
            ),
            "server": self.server.removeprefix("https://"),
        }

    def set_server(self, value: str) -> None:
        server = validate_magnus_server(value)
        if server != self.server:
            self._reset()
        self.server = server

    def set_profile(self, profile_id: str, server: str) -> None:
        safe_server = validate_magnus_server(server)
        if profile_id != self.profile_id or safe_server != self.server:
            self._reset()
        self.profile_id = profile_id
        self.server = safe_server

    def clear_profile(self) -> None:
        self.profile_id = ""
        self.server = ""
        self._reset()

    def reset_access(self) -> None:
        self._reset()

    def probe(self) -> bool:
        if not self.server or not self.cookie_provider.status().get("configured"):
            self._access = "unknown"
            return False
        try:
            with self.cookie_provider.authenticated_cookie() as cookie:
                descriptor = self.http.get_json(
                    self.server, MAGNUS_API_PREFIX + "/GetServer", cookie
                )
            if not isinstance(descriptor, dict):
                raise MagnusError("invalid_magnus_response")
        except MagnusUnavailableError:
            self._access = "unavailable"
            self._targets.clear()
            return False
        except RockSessionError:
            self._access = "error"
            self._targets.clear()
            return False
        except MagnusError:
            self._access = "error"
            self._targets.clear()
            return False
        self._access = "available"
        return True

    def list_tree(self, path: str = DEFAULT_TREE_PATH) -> list[dict[str, Any]]:
        safe_path = validate_tree_path(path)
        try:
            with self.cookie_provider.authenticated_cookie() as cookie:
                value = self.http.get_json(self.server, "/" + safe_path, cookie)
        except MagnusUnavailableError:
            self._access = "unavailable"
            raise
        except RockSessionError as error:
            self._access = "error"
            raise MagnusError("rock_login_failed") from error
        except MagnusError:
            self._access = "error"
            raise
        if not isinstance(value, list) or len(value) > MAX_TREE_ITEMS:
            raise MagnusError("magnus_response_out_of_bounds")
        self._access = "available"
        return [self._sanitize_tree_item(item) for item in value]

    def read_file(self, path: str) -> bytes:
        safe_path = validate_file_path(path)
        try:
            with self.cookie_provider.authenticated_cookie() as cookie:
                content = self.http.get_bytes(
                    self.server, MAGNUS_API_PREFIX + safe_path, cookie
                )
        except MagnusUnavailableError:
            self._access = "unavailable"
            raise
        except RockSessionError as error:
            self._access = "error"
            raise MagnusError("rock_login_failed") from error
        except MagnusError:
            self._access = "error"
            raise
        self._access = "available"
        return content

    def hash_file(self, path: str) -> str:
        return hashlib.sha256(self.read_file(path)).hexdigest()

    def browse(self, safe_id: str = "") -> dict[str, Any]:
        if safe_id:
            kind, path = self._resolve(safe_id)
            if kind != "folder":
                raise MagnusError("invalid_magnus_item")
            title = PurePosixPath(path).name or "Magnus"
        else:
            path = DEFAULT_TREE_PATH
            title = "Magnus"
        items = self.list_tree(path)
        public_items: list[dict[str, Any]] = []
        for item in items:
            kind = "folder" if item["isFolder"] else "file"
            target_path = item.get("path") if kind == "folder" else item.get("filePath")
            if not isinstance(target_path, str):
                continue
            item_id = self._register(kind, target_path)
            public_items.append(
                {
                    "safeId": item_id,
                    "title": item["displayName"],
                    "kind": kind,
                    "actions": list(item.get("actions", [])),
                }
            )
        return {
            "folderId": safe_id,
            "title": sanitize_text(title, 160),
            "items": public_items,
        }

    def preview(self, safe_id: str) -> dict[str, str]:
        kind, path = self._resolve(safe_id)
        if kind != "file":
            raise MagnusError("invalid_magnus_item")
        content = self.read_file(path)
        if len(content) > MAX_PREVIEW_BYTES or b"\x00" in content:
            raise MagnusError("magnus_preview_unavailable")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise MagnusError("magnus_preview_unavailable") from error
        return {
            "safeId": safe_id,
            "title": PurePosixPath(path).name,
            "content": text,
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    def _reset(self) -> None:
        self._access = "unknown"
        self._targets.clear()

    def _register(self, kind: str, path: str) -> str:
        digest = hmac.new(
            self._key, f"{self.server}\0{kind}\0{path}".encode(), hashlib.sha256
        ).hexdigest()[:32]
        safe_id = "magnus-" + digest
        self._targets[safe_id] = (kind, path)
        self._targets.move_to_end(safe_id)
        while len(self._targets) > MAX_REGISTERED_ITEMS:
            self._targets.popitem(last=False)
        return safe_id

    def _resolve(self, safe_id: str) -> tuple[str, str]:
        clean_id = sanitize_text(safe_id, 100)
        target = self._targets.get(clean_id)
        if target is None:
            raise MagnusError("magnus_item_not_found")
        self._targets.move_to_end(clean_id)
        return target

    def _sanitize_tree_item(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise MagnusError("invalid_magnus_response")
        display_name = sanitize_text(self._field(value, "displayName"), 200)
        is_folder = bool(self._field(value, "isFolder"))
        if not display_name:
            raise MagnusError("invalid_magnus_response")
        item: dict[str, Any] = {
            "displayName": display_name,
            "isFolder": is_folder,
        }
        for key in ("id", "guid"):
            raw = self._field(value, key)
            if raw is not None:
                item[key] = sanitize_text(raw, 100)

        candidates = (
            ("path", "path", self._normalized_tree_path),
            ("uri", "path", self._normalized_tree_path),
            ("filePath", "filePath", self._normalized_file_path),
            ("fileContentUri", "filePath", self._normalized_file_path),
        )
        for source, target, validator in candidates:
            raw = self._field(value, source)
            if isinstance(raw, str) and target not in item:
                try:
                    item[target] = validator(raw)
                except MagnusError:
                    pass

        actions: list[str] = []
        for source, name, prefix in (
            ("buildUri", "build", "/Build/"),
            ("deleteUri", "delete", "/Delete/"),
            ("uploadFileUri", "upload", "/Upload/"),
            ("newFileUri", "newFile", "/NewFile/"),
            ("newFolderUri", "newFolder", "/NewFolder/"),
        ):
            raw = self._field(value, source)
            if isinstance(raw, str) and self._valid_action_uri(raw, prefix):
                actions.append(name)
        item["actions"] = actions
        return item

    def _normalized_tree_path(self, value: str) -> str:
        return validate_tree_path(self._same_origin_path(value))

    def _normalized_file_path(self, value: str) -> str:
        return validate_file_path(self._same_origin_path(value))

    def _same_origin_path(self, value: str) -> str:
        candidate = value.strip()
        if "://" not in candidate:
            return candidate
        parsed = urllib.parse.urlsplit(candidate)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if validate_magnus_server(origin) != self.server or parsed.query or parsed.fragment:
            raise MagnusError("magnus_cross_origin_uri")
        return parsed.path

    def _valid_action_uri(self, value: str, action_prefix: str) -> bool:
        try:
            path = self._same_origin_path(value)
        except MagnusError:
            return False
        return (
            path.startswith(MAGNUS_API_PREFIX + action_prefix)
            and len(path) > len(MAGNUS_API_PREFIX + action_prefix)
            and "\\" not in path
            and not any(part in (".", "..") for part in PurePosixPath(path).parts)
            and all(ord(char) >= 32 for char in path)
        )

    @staticmethod
    def _field(value: dict[str, Any], name: str) -> Any:
        if name in value:
            return value[name]
        pascal = name[0].upper() + name[1:]
        return value.get(pascal)

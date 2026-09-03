from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import stat
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from .contracts import sanitize_text
from .navigation import NavigationError, NavigationTarget, validate_rock_url
from .origin import DEFAULT_ROCK_ORIGIN, OriginError, validate_rock_origin
from .rock_session import RockSessionError
from .version import HTTP_USER_AGENT

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
MAX_ACTION_OUTPUT_BYTES = 64 * 1024
MOBILE_APP_BUILD_PREFIX = MAGNUS_API_PREFIX + "/Build/mobileapps/"
ROCK_LENS_USER_AGENT = HTTP_USER_AGENT


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

    def post_json(self, origin: str, path: str, cookie: str) -> Any: ...


@dataclass(frozen=True)
class MagnusTarget:
    kind: str
    path: str
    title: str
    build_path: str = ""
    view_url: str = ""


@dataclass(frozen=True)
class MagnusBuildOutcome:
    title: str
    message: str
    target: NavigationTarget

    def public_dict(self) -> dict[str, str]:
        return {"title": self.title, "message": self.message}


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
    """Same-origin, redirect-free client for the bounded Magnus surface."""

    def __init__(self, opener: Any | None = None) -> None:
        self._opener = opener

    def get_json(self, origin: str, path: str, cookie: str) -> Any:
        raw = self._get(origin, path, cookie, MAX_TREE_OUTPUT_BYTES)
        try:
            return json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise MagnusError("invalid_magnus_response") from error

    def get_bytes(self, origin: str, path: str, cookie: str) -> bytes:
        return self._request(origin, path, cookie, "GET", MAX_FILE_BYTES)

    def post_json(self, origin: str, path: str, cookie: str) -> Any:
        raw = self._request(
            origin, path, cookie, "POST", MAX_ACTION_OUTPUT_BYTES, data=b""
        )
        try:
            return json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise MagnusError("invalid_magnus_response") from error

    def _get(self, origin: str, path: str, cookie: str, maximum: int) -> bytes:
        return self._request(origin, path, cookie, "GET", maximum)

    def _request(
        self,
        origin: str,
        path: str,
        cookie: str,
        method: str,
        maximum: int,
        data: bytes | None = None,
    ) -> bytes:
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
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Cookie": cookie,
            "User-Agent": ROCK_LENS_USER_AGENT,
        }
        if method == "POST":
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            safe_origin + path,
            headers=headers,
            data=data,
            method=method,
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
    """Native Magnus reads plus explicitly confirmed mobile-app builds."""

    def __init__(
        self,
        cookie_provider: CookieProvider,
        server: str | None = None,
        http: MagnusHttp | None = None,
        downloads_dir: Path | None = None,
    ) -> None:
        self.cookie_provider = cookie_provider
        self.server = validate_magnus_server(server) if server else ""
        self.profile_id = ""
        self.http = http or MagnusHttpClient()
        self.downloads_dir = downloads_dir or Path.home() / "Downloads"
        self._access = "unknown"
        self._key = secrets.token_bytes(32)
        self._targets: OrderedDict[str, MagnusTarget] = OrderedDict()

    def status(self) -> dict[str, Any]:
        session_status = self.cookie_provider.status()
        configured = bool(session_status.get("configured")) and bool(self.server)
        return {
            "available": configured and self._access == "available",
            "configured": configured,
            "state": self._access if configured else "signed_out",
            "mode": "controlled",
            "capabilities": (
                [
                    "browse",
                    "preview",
                    "hash",
                    "download",
                    "copy",
                    "open",
                    "mobile_app_build",
                ]
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
            target = self._resolve(safe_id)
            if target.kind != "folder":
                raise MagnusError("invalid_magnus_item")
            path = target.path
            title = target.title
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
            if kind == "folder":
                actions = ["build"] if item.get("buildPath") else []
            else:
                actions = ["download", "copyHash"]
                if item.get("viewUrl"):
                    actions.append("view")
            item_id = self._register(
                MagnusTarget(
                    kind=kind,
                    path=target_path,
                    title=item["displayName"],
                    build_path=str(item.get("buildPath", "")),
                    view_url=str(item.get("viewUrl", "")),
                )
            )
            public_items.append(
                {
                    "safeId": item_id,
                    "title": item["displayName"],
                    "kind": kind,
                    "actions": actions,
                }
            )
        return {
            "folderId": safe_id,
            "title": sanitize_text(title, 160),
            "items": public_items,
        }

    def preview(self, safe_id: str) -> dict[str, Any]:
        target = self._resolve(safe_id)
        if target.kind != "file":
            raise MagnusError("invalid_magnus_item")
        content = self.read_file(target.path)
        text = ""
        preview_available = len(content) <= MAX_PREVIEW_BYTES and b"\x00" not in content
        if preview_available:
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                preview_available = False
        actions = ["download", "copyHash"]
        if preview_available:
            actions.append("copy")
        if target.view_url:
            actions.append("view")
        return {
            "safeId": safe_id,
            "title": target.title,
            "content": text,
            "sha256": hashlib.sha256(content).hexdigest(),
            "sizeBytes": len(content),
            "previewAvailable": preview_available,
            "actions": actions,
        }

    def download(self, safe_id: str) -> dict[str, Any]:
        target = self._resolve_file(safe_id)
        content = self.read_file(target.path)
        filename = self._safe_filename(target.title)
        directory_descriptor = self._open_downloads_directory()
        destination_descriptor: int | None = None
        saved_as = ""
        try:
            stem = Path(filename).stem
            suffix = Path(filename).suffix
            for index in range(1_000):
                saved_as = filename if index == 0 else f"{stem} ({index}){suffix}"
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
                if hasattr(os, "O_NOFOLLOW"):
                    flags |= os.O_NOFOLLOW
                try:
                    destination_descriptor = os.open(
                        saved_as, flags, 0o600, dir_fd=directory_descriptor
                    )
                    break
                except FileExistsError:
                    continue
            if destination_descriptor is None:
                raise MagnusError("magnus_download_failed")
            with os.fdopen(destination_descriptor, "wb") as stream:
                destination_descriptor = None
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except (OSError, MagnusError) as error:
            if destination_descriptor is not None:
                os.close(destination_descriptor)
            if saved_as:
                try:
                    os.unlink(saved_as, dir_fd=directory_descriptor)
                except OSError:
                    pass
            if isinstance(error, MagnusError):
                raise
            raise MagnusError("magnus_download_failed") from error
        finally:
            os.close(directory_descriptor)
        return {
            "title": target.title,
            "savedAs": saved_as,
            "folder": "Downloads",
            "sizeBytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    def copy_value(self, safe_id: str, value: str) -> str:
        preview = self.preview(safe_id)
        if value == "hash":
            return str(preview["sha256"])
        if value == "content" and preview["previewAvailable"]:
            return str(preview["content"])
        raise MagnusError("magnus_copy_unavailable")

    def view_target(self, safe_id: str) -> NavigationTarget:
        target = self._resolve_file(safe_id)
        if not target.view_url:
            raise MagnusError("magnus_view_unavailable")
        return NavigationTarget(target.title, "Magnus File", 80, target.view_url)

    def build(self, safe_id: str) -> MagnusBuildOutcome:
        target = self._resolve(safe_id)
        if target.kind != "folder" or not target.build_path:
            raise MagnusError("magnus_build_unavailable")
        return self._run_build(target.title, target.build_path)

    def build_recent(self, url: str, title: str) -> MagnusBuildOutcome:
        build_path = self._validated_mobile_build_path(url)
        return self._run_build(sanitize_text(title, 160), build_path)

    def _reset(self) -> None:
        self._access = "unknown"
        self._targets.clear()

    def _register(self, target: MagnusTarget) -> str:
        digest = hmac.new(
            self._key,
            f"{self.server}\0{target.kind}\0{target.path}\0{target.build_path}\0{target.view_url}".encode(),
            hashlib.sha256,
        ).hexdigest()[:32]
        safe_id = "magnus-" + digest
        self._targets[safe_id] = target
        self._targets.move_to_end(safe_id)
        while len(self._targets) > MAX_REGISTERED_ITEMS:
            self._targets.popitem(last=False)
        return safe_id

    def _resolve(self, safe_id: str) -> MagnusTarget:
        clean_id = sanitize_text(safe_id, 100)
        target = self._targets.get(clean_id)
        if target is None:
            raise MagnusError("magnus_item_not_found")
        self._targets.move_to_end(clean_id)
        return target

    def _resolve_file(self, safe_id: str) -> MagnusTarget:
        target = self._resolve(safe_id)
        if target.kind != "file":
            raise MagnusError("invalid_magnus_item")
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
            (
                ("path", "path", self._normalized_tree_path),
                ("uri", "path", self._normalized_tree_path),
            )
            if is_folder
            else (
                ("filePath", "filePath", self._normalized_file_path),
                ("fileContentUri", "filePath", self._normalized_file_path),
                ("uri", "filePath", self._normalized_file_path),
            )
        )
        for source, target, validator in candidates:
            raw = self._field(value, source)
            if isinstance(raw, str) and target not in item:
                try:
                    item[target] = validator(raw)
                except MagnusError:
                    pass

        raw_build = self._field(value, "buildUri")
        if is_folder and isinstance(raw_build, str):
            try:
                item["buildPath"] = self._validated_mobile_build_path(raw_build)
            except MagnusError:
                pass
        raw_view = self._field(value, "remoteViewUri")
        if not is_folder and isinstance(raw_view, str):
            try:
                item["viewUrl"] = validate_rock_url(raw_view, self.server)
            except NavigationError:
                pass
        item["actions"] = (
            (["build"] if item.get("buildPath") else [])
            if is_folder
            else (
                ["download", "copyHash"]
                + (["view"] if item.get("viewUrl") else [])
            )
        )
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

    def _validated_mobile_build_path(self, value: str) -> str:
        path = self._same_origin_path(value)
        app_id = path.removeprefix(MOBILE_APP_BUILD_PREFIX)
        if (
            not path.startswith(MOBILE_APP_BUILD_PREFIX)
            or not app_id.isdigit()
            or int(app_id) < 1
            or "/" in app_id
        ):
            raise MagnusError("magnus_build_uri_not_allowed")
        return path

    def _run_build(self, title: str, build_path: str) -> MagnusBuildOutcome:
        if not title:
            raise MagnusError("invalid_magnus_item")
        safe_path = self._validated_mobile_build_path(build_path)
        try:
            with self.cookie_provider.authenticated_cookie() as cookie:
                result = self.http.post_json(self.server, safe_path, cookie)
        except MagnusUnavailableError:
            self._access = "unavailable"
            raise
        except RockSessionError as error:
            self._access = "error"
            raise MagnusError("rock_login_failed") from error
        except MagnusError:
            self._access = "error"
            raise
        if not isinstance(result, dict):
            raise MagnusError("invalid_magnus_response")
        successful = self._field(result, "actionSuccessful")
        message = sanitize_text(self._field(result, "responseMessage"), 300)
        if successful is not True:
            raise MagnusError("magnus_build_failed")
        self._access = "available"
        return MagnusBuildOutcome(
            title=title,
            message=message or "Build started successfully.",
            target=NavigationTarget(
                "Deploy " + title,
                "Magnus Build",
                5,
                self.server + safe_path,
            ),
        )

    @staticmethod
    def _safe_filename(value: str) -> str:
        candidate = PurePosixPath(sanitize_text(value, 160)).name
        if candidate in ("", ".", ".."):
            return "magnus-download"
        return candidate

    def _open_downloads_directory(self) -> int:
        try:
            self.downloads_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            flags = os.O_RDONLY
            if hasattr(os, "O_DIRECTORY"):
                flags |= os.O_DIRECTORY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self.downloads_dir, flags)
            info = os.fstat(descriptor)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                os.close(descriptor)
                raise MagnusError("magnus_download_failed")
            return descriptor
        except OSError as error:
            raise MagnusError("magnus_download_failed") from error

    @staticmethod
    def _field(value: dict[str, Any], name: str) -> Any:
        if name in value:
            return value[name]
        pascal = name[0].upper() + name[1:]
        return value.get(pascal)

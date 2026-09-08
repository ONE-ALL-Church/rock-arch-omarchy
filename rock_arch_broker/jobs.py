from __future__ import annotations

import http.client
import json
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from .contracts import sanitize_text
from .http_security import (
    HttpSecurityError,
    decode_bounded_json,
    redirect_free_opener,
    validate_rock_cookie_header,
)
from .navigation import NavigationTarget
from .origin import validate_rock_origin
from .rock_rest_adapter import CookieProvider
from .rock_session import RockSessionError
from .version import HTTP_USER_AGENT

JOB_BLOCK_TYPE = "9b90f2d1-0c7b-4f08-a808-8ba4c9a70a20"
JOBS_PAGE = "c58ada1a-6322-4998-8fed-c3565de87efa"
MAX_RESPONSE = 512 * 1024
MAX_PLACEMENTS = 8
ACCESS_SECONDS = 60
DRAFT_SECONDS = 120
JOB_FIELDS = "Id,Guid,Name,LastStatus,LastRunDateTime,LastRunDurationSeconds"
ACTION_PATH = re.compile(r"/api/v2/blockactions/([0-9a-f-]{36})/([0-9a-f-]{36})/(RefreshObsidianBlockInitialization|RunNow)")


class JobError(Exception):
    """A stable error code without Rock response bodies or credentials."""


def _guid(value: object) -> str:
    try:
        parsed = UUID(str(value))
        return str(parsed) if parsed.int else ""
    except (ValueError, TypeError, AttributeError):
        return ""


def _id(value: object) -> bool:
    return type(value) is int and 0 < value <= 2_147_483_647


class JobClient(Protocol):
    def request(self, origin: str, path: str, params: dict[str, str], cookie: str,
                body: dict[str, str] | None = None) -> Any: ...


class JobHttpClient:
    """Exact discovery/status reads and one explicitly confirmed RunNow POST."""

    def __init__(self, opener: Any = None) -> None:
        self._opener = opener

    def request(self, origin: str, path: str, params: dict[str, str], cookie: str,
                body: dict[str, str] | None = None) -> Any:
        action = ACTION_PATH.fullmatch(path)
        if action and (not _guid(action[1]) or not _guid(action[2])):
            raise JobError("job_request_invalid")
        if body is not None:
            if (not action or action[3] != "RunNow" or params
                    or set(body) != {"key"} or not _guid(body["key"])):
                raise JobError("job_request_invalid")
        elif (action and (action[3] != "RefreshObsidianBlockInitialization" or params)) or (
            not action and (path not in {"/api/BlockTypes", "/api/Blocks", "/api/Pages", "/api/ServiceJobs"}
                           or not set(params).issubset({"$filter", "$select", "$top"}))
        ):
            raise JobError("job_request_invalid")
        query = urllib.parse.urlencode(params)
        try:
            safe_cookie = validate_rock_cookie_header(cookie)
        except HttpSecurityError as error:
            raise JobError("job_request_invalid") from error
        request = urllib.request.Request(
            validate_rock_origin(origin) + path + ("?" + query if query else ""),
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Cookie": safe_cookie, "Accept": "application/json",
                     "Content-Type": "application/json", "User-Agent": HTTP_USER_AGENT},
            method="POST" if body is not None else "GET",
        )
        failure = "job_run_uncertain" if body is not None else "job_access_unavailable"
        try:
            with redirect_free_opener(self._opener).open(request, timeout=15) as response:
                raw = response.read(MAX_RESPONSE + 1)
                content_type = response.headers.get("Content-Type", "")
            if len(raw) > MAX_RESPONSE or (raw and "application/json" not in content_type.lower()):
                raise JobError(failure)
            value = decode_bounded_json(raw) if raw else None
            if body is not None and value is not None:
                raise JobError(failure)
            return value
        except urllib.error.HTTPError as error:
            if error.code in {401, 403}:
                raise JobError("job_access_denied") from None
            if body is not None and error.code in {400, 404, 405, 409, 429}:
                raise JobError("job_run_rejected") from None
            raise JobError(failure) from None
        except (OSError, ValueError, http.client.HTTPException) as error:
            raise JobError(failure) from error


@dataclass(frozen=True)
class Placement:
    page: str
    block: str

    def action(self, name: str) -> str:
        return f"/api/v2/blockactions/{self.page}/{self.block}/{name}"


@dataclass(frozen=True)
class JobDraft:
    number: int
    guid: str
    title: str
    placement: Placement
    deadline: float


@dataclass(frozen=True)
class JobRunOutcome:
    target: NavigationTarget

    def public_dict(self) -> dict[str, Any]:
        return {"state": "requested", "title": self.target.title, "completionVerified": False}


class JobManager:
    def __init__(self, session: CookieProvider, http: JobClient | None = None) -> None:
        self._session = session
        self._http = http or JobHttpClient()
        self._origin: str | None = None
        self.clear()

    def clear(self) -> None:
        self._placement: Placement | None = None
        self._access: dict[str, Any] = {"available": False, "state": "unchecked"}
        self._deadline = 0.0
        self._drafts: dict[str, JobDraft] = {}

    def set_origin(self, origin: str | None) -> None:
        self._origin = validate_rock_origin(origin) if origin else None
        self.clear()

    def _read(self, path: str, params: dict[str, str], cookie: str) -> Any:
        if not self._origin:
            raise JobError("job_access_unavailable")
        return self._http.request(self._origin, path, params, cookie)

    def _rows(self, path: str, params: dict[str, str], cookie: str, maximum: int) -> list[dict[str, Any]]:
        rows = self._read(path, {**params, "$top": str(maximum + 1)}, cookie)
        if not isinstance(rows, list) or len(rows) > maximum or any(not isinstance(r, dict) for r in rows):
            raise JobError("job_discovery_ambiguous")
        return rows

    def _verify(self, placement: Placement, cookie: str) -> None:
        config = self._read(placement.action("RefreshObsidianBlockInitialization"), {}, cookie)
        if (not isinstance(config, dict) or _guid(config.get("blockGuid")) != placement.block
                or _guid(config.get("blockTypeGuid")) != JOB_BLOCK_TYPE):
            raise JobError("job_access_unavailable")
        values = config.get("configurationValues")
        # Rock sets these two flags from the Jobs block's EDIT permission.
        # Search/VIEW access alone is deliberately insufficient for a trigger.
        if (not isinstance(values, dict) or values.get("errorMessage")
                or values.get("isAddEnabled") is not True or values.get("isDeleteEnabled") is not True):
            raise JobError("job_access_denied")

    def access(self, refresh: bool = False) -> dict[str, Any]:
        if not refresh and time.monotonic() < self._deadline:
            return dict(self._access)
        self._placement = None
        self._access = {"available": False, "state": "unavailable"}
        if not self._origin:
            return dict(self._access)
        try:
            with self._session.authenticated_cookie() as cookie:
                types = self._rows("/api/BlockTypes", {"$filter": f"Guid eq guid'{JOB_BLOCK_TYPE}'", "$select": "Id,Guid"}, cookie, 1)
                if not types or not _id(types[0].get("Id")) or _guid(types[0].get("Guid")) != JOB_BLOCK_TYPE:
                    raise JobError("job_access_unavailable")
                blocks = self._rows("/api/Blocks", {"$filter": f"BlockTypeId eq {types[0]['Id']}", "$select": "Guid,PageId,BlockTypeId"}, cookie, MAX_PLACEMENTS)
                available: set[Placement] = set()
                denied = False
                for block in blocks:
                    if block.get("BlockTypeId") != types[0]["Id"] or not _id(block.get("PageId")) or not _guid(block.get("Guid")):
                        continue
                    pages = self._rows("/api/Pages", {"$filter": f"Id eq {block['PageId']}", "$select": "Id,Guid"}, cookie, 1)
                    if not pages or pages[0].get("Id") != block["PageId"] or not _guid(pages[0].get("Guid")):
                        continue
                    placement = Placement(_guid(pages[0]["Guid"]), _guid(block["Guid"]))
                    try:
                        self._verify(placement, cookie)
                    except JobError as error:
                        if str(error) == "job_access_denied":
                            denied = True
                            continue
                        raise
                    available.add(placement)
                preferred = {p for p in available if p.page == JOBS_PAGE}
                choices = preferred or available
                if len(choices) > 1:
                    raise JobError("job_discovery_ambiguous")
                if not choices:
                    raise JobError("job_access_denied" if denied else "job_access_unavailable")
                self._placement = next(iter(choices))
                self._access = {"available": True, "state": "ready"}
        except (JobError, RockSessionError) as error:
            code = str(error) if isinstance(error, JobError) else "job_access_unavailable"
            self._access = {"available": False, "state": "unavailable", "error": code}
        self._deadline = time.monotonic() + ACCESS_SECONDS
        return dict(self._access)

    def _job(self, number: int, cookie: str) -> dict[str, Any]:
        if not _id(number):
            raise JobError("job_not_found")
        rows = self._rows("/api/ServiceJobs", {"$filter": f"Id eq {number}", "$select": JOB_FIELDS}, cookie, 1)
        if not rows or rows[0].get("Id") != number or not _guid(rows[0].get("Guid")) or not sanitize_text(rows[0].get("Name"), 160):
            raise JobError("job_not_found")
        return rows[0]

    def prepare(self, number: int) -> dict[str, Any]:
        access = self.access(refresh=True)
        if not access["available"] or self._placement is None:
            raise JobError(access.get("error", "job_access_unavailable"))
        with self._session.authenticated_cookie() as cookie:
            row = self._job(number, cookie)
        self._drafts = {k: v for k, v in self._drafts.items() if v.deadline > time.monotonic()}
        if len(self._drafts) >= 16:
            raise JobError("job_too_many_drafts")
        token = "job-draft-" + secrets.token_hex(16)
        title = sanitize_text(row["Name"], 160)
        self._drafts[token] = JobDraft(number, _guid(row["Guid"]), title, self._placement, time.monotonic() + DRAFT_SECONDS)
        return {"state": "confirm", "draftId": token, "title": title, "confirmationRequired": True}

    def run(self, token: object, confirmed: bool) -> JobRunOutcome:
        if not confirmed:
            raise JobError("job_confirmation_required")
        draft = self._drafts.pop(token, None) if isinstance(token, str) else None
        if draft is None or draft.deadline <= time.monotonic():
            raise JobError("job_draft_expired")
        access = self.access(refresh=True)
        if not access["available"] or self._placement != draft.placement:
            raise JobError("job_access_changed")
        with self._session.authenticated_cookie() as cookie:
            row = self._job(draft.number, cookie)
            if _guid(row["Guid"]) != draft.guid or sanitize_text(row["Name"], 160) != draft.title:
                raise JobError("job_changed")
            if draft.deadline <= time.monotonic():
                raise JobError("job_draft_expired")
            assert self._origin is not None
            self._http.request(self._origin, draft.placement.action("RunNow"), {}, cookie, {"key": draft.guid})
        return JobRunOutcome(NavigationTarget(
            draft.title, "Scheduled Job", 40, f"{self._origin}/admin/system/jobs/{draft.number}"
        ))

    def status(self, number: int) -> dict[str, Any]:
        with self._session.authenticated_cookie() as cookie:
            row = self._job(number, cookie)
        return {"state": "status", "title": sanitize_text(row["Name"], 160),
                "lastStatus": sanitize_text(row.get("LastStatus"), 80),
                "lastRunAt": sanitize_text(row.get("LastRunDateTime"), 80),
                "completionVerified": False}

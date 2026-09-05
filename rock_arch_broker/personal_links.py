from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from .http_security import (
    HttpSecurityError,
    decode_bounded_json,
    redirect_free_opener,
    validate_rock_cookie_header,
)
from .navigation import NavigationError, validate_rock_url
from .origin import validate_rock_origin
from .rock_rest_adapter import CookieProvider
from .version import HTTP_USER_AGENT

MAX_RESPONSE = 2 * 1024 * 1024
MAX_SECTIONS = 100
DRAFT_SECONDS = 600
CURRENT_PERSON = "/api/People/GetCurrentPerson"
SECTIONS = "/api/PersonalLinkSections"
LINKS = "/api/PersonalLinks"
NEW_SECTION = "new-links"
LINK_FIELDS = "Id,Name,Url,SectionId,PersonAliasId"


class PersonalLinkError(Exception):
    """A stable code without Rock response bodies, identities, or URLs."""


class LinkClient(Protocol):
    def get(
        self, origin: str, path: str, params: dict[str, str], cookie: str
    ) -> Any: ...

    def create(
        self, origin: str, path: str, body: dict[str, Any], cookie: str
    ) -> int: ...


class PersonalLinkHttpClient:
    """Only the four reads and two creates needed for personal bookmarks."""

    def __init__(self, opener: Any = None) -> None:
        self._opener = opener

    def get(self, origin: str, path: str, params: dict[str, str], cookie: str) -> Any:
        if (
            path not in {CURRENT_PERSON, SECTIONS, LINKS}
            or (path == CURRENT_PERSON and params)
            or not set(params).issubset(
                {"$filter", "$select", "$expand", "$orderby", "$top"}
            )
        ):
            raise PersonalLinkError("personal_link_request_invalid")
        return self._request(origin, path, params, cookie)

    def create(self, origin: str, path: str, body: dict[str, Any], cookie: str) -> int:
        fields = (
            {"Name", "PersonAliasId", "IsShared"}
            if path == SECTIONS
            else {"Name", "Url", "PersonAliasId", "SectionId", "Order"}
        )
        if (
            path not in {SECTIONS, LINKS}
            or set(body) != fields
            or (path == SECTIONS and body["IsShared"] is not False)
        ):
            raise PersonalLinkError("personal_link_request_invalid")
        value = self._request(origin, path, {}, cookie, body)
        if not _positive_id(value):
            raise PersonalLinkError("personal_link_save_uncertain")
        return value

    def _request(
        self,
        origin: str,
        path: str,
        params: dict[str, str],
        cookie: str,
        body: dict[str, Any] | None = None,
    ) -> Any:
        try:
            safe_cookie = validate_rock_cookie_header(cookie)
        except HttpSecurityError as error:
            raise PersonalLinkError("invalid_rock_cookie") from error
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(
            validate_rock_origin(origin) + path + ("?" + query if query else ""),
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Cookie": safe_cookie,
                "User-Agent": HTTP_USER_AGENT,
            },
            method="POST" if body is not None else "GET",
        )
        failure = (
            "personal_link_save_uncertain"
            if body is not None
            else "personal_links_unavailable"
        )
        try:
            with redirect_free_opener(self._opener).open(
                request, timeout=20
            ) as response:
                raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                raise PersonalLinkError(failure)
            return decode_bounded_json(raw)
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
            if status in {401, 403, 404, 405}:
                raise PersonalLinkError("personal_links_not_authorized") from error
            if status == 400:
                raise PersonalLinkError(
                    "personal_link_rejected"
                    if body is not None
                    else "personal_links_unavailable"
                ) from error
            raise PersonalLinkError(failure) from error
        except (
            OSError,
            urllib.error.URLError,
            http.client.HTTPException,
            HttpSecurityError,
        ) as error:
            # POST is deliberately never retried: a timeout can follow a commit.
            raise PersonalLinkError(failure) from error


def _positive_id(value: object) -> bool:
    return type(value) is int and 0 < value <= 2_147_483_647


def _name(value: object, *, empty: bool = False) -> str:
    if not isinstance(value, str):
        raise PersonalLinkError("personal_link_name_invalid")
    name = value.strip()
    try:
        size = len(name.encode("utf-16-le")) // 2
    except UnicodeError as error:
        raise PersonalLinkError("personal_link_name_invalid") from error
    if (
        (not name and not empty)
        or size > 100
        or any(ord(char) < 32 or ord(char) == 127 for char in name)
    ):
        raise PersonalLinkError("personal_link_name_invalid")
    return name


def prefill_name(title: str) -> str:
    """Fit a search title to Rock's Name limit without splitting a surrogate pair."""
    return title.encode("utf-16-le")[:200].decode("utf-16-le", errors="ignore").strip()


@dataclass(frozen=True)
class _Draft:
    person_id: int
    alias_id: int
    sections: frozenset[str]
    default_section: str
    deadline: float
    kind: str = "link"


class PersonalLinkManager:
    """Profile-scoped, single-use drafts for explicitly confirmed additions."""

    def __init__(
        self, session: CookieProvider, client: LinkClient | None = None
    ) -> None:
        self._session = session
        self._client = client or PersonalLinkHttpClient()
        self._origin = ""
        self._drafts: dict[str, _Draft] = {}
        self._secret = secrets.token_bytes(32)

    def clear(self) -> None:
        self._drafts.clear()
        self._secret = secrets.token_bytes(32)

    def set_origin(self, origin: str | None) -> None:
        self.clear()
        self._origin = validate_rock_origin(origin) if origin else ""

    def _identity(self, cookie: str) -> tuple[int, int]:
        value = self._client.get(self._origin, CURRENT_PERSON, {}, cookie)
        if (
            not isinstance(value, dict)
            or not _positive_id(value.get("Id"))
            or not _positive_id(value.get("PrimaryAliasId"))
        ):
            raise PersonalLinkError("personal_links_not_authorized")
        # Discard all other current-person fields; they never reach UI or disk.
        return value["Id"], value["PrimaryAliasId"]

    def _section_id(self, person: int, section: int) -> str:
        digest = hmac.new(
            self._secret, f"{person}:{section}".encode(), hashlib.sha256
        ).hexdigest()[:32]
        return "link-section-" + digest

    def _sections(self, person: int, alias: int, cookie: str) -> list[dict[str, Any]]:
        value = self._client.get(
            self._origin,
            SECTIONS,
            {
                "$filter": f"IsShared eq false and PersonAliasId eq {alias}",
                "$select": "Id,Name,IsShared,PersonAliasId",
                "$orderby": "Name,Id",
                "$top": str(MAX_SECTIONS + 1),
            },
            cookie,
        )
        if not isinstance(value, list) or len(value) > MAX_SECTIONS:
            raise PersonalLinkError("personal_link_sections_invalid")
        result = []
        for item in value:
            if (
                not isinstance(item, dict)
                or not _positive_id(item.get("Id"))
                or item.get("IsShared") is not False
            ):
                raise PersonalLinkError("personal_link_sections_invalid")
            if (
                type(item.get("PersonAliasId")) is not int
                or item["PersonAliasId"] != alias
            ):
                raise PersonalLinkError("personal_link_sections_invalid")
            result.append(
                {
                    "id": item["Id"],
                    "name": _name(item.get("Name")),
                    "safeId": self._section_id(person, item["Id"]),
                }
            )
        return result

    def prepare(self, name: object = "", url: object = "") -> dict[str, Any]:
        if not self._origin:
            raise PersonalLinkError("rock_login_required")
        clean_name = _name(name, empty=True)
        clean_url = self._url(url) if url != "" else ""
        with self._session.authenticated_cookie() as cookie:
            person, alias = self._identity(cookie)
            sections = self._sections(person, alias, cookie)
        public = [{"safeId": item["safeId"], "name": item["name"]} for item in sections]
        if not public:
            public = [{"safeId": NEW_SECTION, "name": "Links (new personal section)"}]
        default = next(
            (item["safeId"] for item in public if item["name"] == "Links"),
            public[0]["safeId"],
        )
        draft_id = self._store_draft(person, alias, public, default, "link")
        return {
            "draftId": draft_id,
            "name": clean_name,
            "url": clean_url,
            "sections": public,
            "sectionId": default,
            "expiresInSeconds": DRAFT_SECONDS,
        }

    def list_sections(self) -> list[dict[str, Any]]:
        """Broker-internal section metadata, including empty private sections."""
        if not self._origin:
            raise PersonalLinkError("rock_login_required")
        with self._session.authenticated_cookie() as cookie:
            person, alias = self._identity(cookie)
            return self._sections(person, alias, cookie)

    def prepare_section(self, name: object = "") -> dict[str, Any]:
        if not self._origin:
            raise PersonalLinkError("rock_login_required")
        clean_name = _name(name, empty=True)
        with self._session.authenticated_cookie() as cookie:
            person, alias = self._identity(cookie)
            self._sections(person, alias, cookie)
        return {
            "draftId": self._store_draft(person, alias, [], "", "section"),
            "name": clean_name,
            "kind": "section",
            "sections": [],
            "expiresInSeconds": DRAFT_SECONDS,
        }

    def _store_draft(
        self,
        person: int,
        alias: int,
        public: list[dict[str, Any]],
        default: str,
        kind: str,
    ) -> str:
        now = time.monotonic()
        self._drafts = {
            key: value for key, value in self._drafts.items() if value.deadline > now
        }
        if len(self._drafts) >= 16:
            del self._drafts[next(iter(self._drafts))]
        draft_id = secrets.token_urlsafe(24)
        self._drafts[draft_id] = _Draft(
            person,
            alias,
            frozenset(item["safeId"] for item in public),
            default,
            now + DRAFT_SECONDS,
            kind,
        )
        return draft_id

    def _draft(self, draft_id: object, kind: str, confirmed: bool) -> _Draft:
        if confirmed is not True:
            raise PersonalLinkError("personal_link_confirmation_required")
        draft = self._drafts.get(draft_id) if isinstance(draft_id, str) else None
        if draft is None or draft.deadline <= time.monotonic() or draft.kind != kind:
            raise PersonalLinkError("personal_link_draft_expired")
        return draft

    def _check_account(self, draft: _Draft, cookie: str) -> tuple[int, int]:
        person, alias = self._identity(cookie)
        if (person, alias) != (draft.person_id, draft.alias_id):
            self.clear()
            raise PersonalLinkError("personal_link_account_changed")
        return person, alias

    def save_section(
        self, draft_id: object, name: object, *, confirmed: bool
    ) -> dict[str, Any]:
        draft = self._draft(draft_id, "section", confirmed)
        clean_name = _name(name)
        with self._session.authenticated_cookie() as cookie:
            person, alias = self._check_account(draft, cookie)
            sections = self._sections(person, alias, cookie)
            section = next(
                (
                    item
                    for item in sections
                    if item["name"].casefold() == clean_name.casefold()
                ),
                None,
            )
            already_saved = section is not None
            if section is None and len(sections) >= MAX_SECTIONS:
                raise PersonalLinkError("personal_section_limit")
            del self._drafts[str(draft_id)]
            if section is None:
                section = self._create_section(person, alias, clean_name, cookie)
        return {
            "saved": True,
            "alreadySaved": already_saved,
            "name": section["name"],
            "sectionId": section["safeId"],
            "_sectionId": section["id"],
        }

    def _create_section(
        self, person: int, alias: int, name: str, cookie: str
    ) -> dict[str, Any]:
        number = self._client.create(
            self._origin,
            SECTIONS,
            {
                "Name": name,
                "PersonAliasId": alias,
                "IsShared": False,
            },
            cookie,
        )
        try:
            sections = self._sections(person, alias, cookie)
            section = next((item for item in sections if item["id"] == number), None)
            if section is None or section["name"] != name:
                raise PersonalLinkError("personal_link_save_uncertain")
        except PersonalLinkError as error:
            raise PersonalLinkError("personal_link_save_uncertain") from error
        return section

    def _url(self, value: object) -> str:
        if not isinstance(value, str) or len(value) > 2048:
            raise PersonalLinkError("personal_link_url_invalid")
        try:
            url = validate_rock_url(value, self._origin)
            if len(url.encode("utf-16-le")) // 2 > 2048:
                raise PersonalLinkError("personal_link_url_invalid")
            return url
        except (NavigationError, UnicodeError) as error:
            raise PersonalLinkError("personal_link_url_invalid") from error

    def save(
        self,
        draft_id: object,
        name: object,
        url: object,
        section_id: object,
        *,
        confirmed: bool,
    ) -> dict[str, Any]:
        draft = self._draft(draft_id, "link", confirmed)
        clean_name, clean_url = _name(name), self._url(url)
        selected = draft.default_section if section_id is None else section_id
        if not isinstance(selected, str) or selected not in draft.sections:
            raise PersonalLinkError("personal_link_section_changed")
        with self._session.authenticated_cookie() as cookie:
            person, alias = self._check_account(draft, cookie)
            sections = self._sections(person, alias, cookie)
            section = next(
                (item for item in sections if item["safeId"] == selected), None
            )
            if selected == NEW_SECTION:
                section = next(
                    (item for item in sections if item["name"] == "Links"), None
                )
            elif section is None:
                raise PersonalLinkError("personal_link_section_changed")
            # Consume before any write. Interrupted or replayed requests cannot
            # resubmit the same mutation, including creation of a first section.
            del self._drafts[str(draft_id)]
            if section is None:
                section = self._create_section(person, alias, "Links", cookie)
            number = section["id"]
            # A deliberate retry after a lost response detects an existing URL.
            quoted_url = clean_url.replace("'", "''")
            rows = self._read_links(
                alias, f"SectionId eq {number} and Url eq '{quoted_url}'", cookie
            )
            if rows:
                self._verify_link(rows[0], alias, number, clean_url)
                return {
                    "saved": True,
                    "alreadySaved": True,
                    "name": _name(rows[0].get("Name")),
                    "section": section["name"],
                }
            created = self._client.create(
                self._origin,
                LINKS,
                {
                    "Name": clean_name,
                    "Url": clean_url,
                    "PersonAliasId": alias,
                    "SectionId": number,
                    "Order": 0,
                },
                cookie,
            )
            try:
                rows = self._read_links(alias, f"Id eq {created}", cookie)
                if len(rows) != 1 or rows[0].get("Id") != created:
                    raise PersonalLinkError("personal_link_save_uncertain")
                self._verify_link(rows[0], alias, number, clean_url)
                if rows[0].get("Name") != clean_name:
                    raise PersonalLinkError("personal_link_save_uncertain")
            except PersonalLinkError as error:
                raise PersonalLinkError("personal_link_save_uncertain") from error
        return {
            "saved": True,
            "alreadySaved": False,
            "name": clean_name,
            "section": section["name"],
        }

    def _read_links(
        self, alias: int, condition: str, cookie: str
    ) -> list[dict[str, Any]]:
        value = self._client.get(
            self._origin,
            LINKS,
            {
                "$filter": f"PersonAliasId eq {alias} and {condition}",
                "$select": LINK_FIELDS,
                "$top": "1",
            },
            cookie,
        )
        if (
            not isinstance(value, list)
            or len(value) > 1
            or any(not isinstance(item, dict) for item in value)
        ):
            raise PersonalLinkError("personal_links_unavailable")
        return value

    @staticmethod
    def _verify_link(item: dict[str, Any], alias: int, section: int, url: str) -> None:
        if (
            not all(
                _positive_id(item.get(key))
                for key in ("Id", "PersonAliasId", "SectionId")
            )
            or item.get("PersonAliasId") != alias
            or item.get("SectionId") != section
            or item.get("Url") != url
        ):
            raise PersonalLinkError("personal_link_save_uncertain")

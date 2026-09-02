from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Protocol

from .contracts import (
    ALLOWED_LINK_KEYS,
    ALLOWED_PERSON_KEYS,
    ALLOWED_RESULT_KEYS,
    allowlist,
    sanitize_text,
)
from .magnus_adapter import MagnusError
from .navigation import NavigationError, NavigationTarget, clean_target
from .origin import DEFAULT_ROCK_ORIGIN, OriginError, validate_rock_origin

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_TARGETS = 256
MAX_PERSONAL_LINKS = 200
ROWS_PER_CATEGORY = 3
ROCK_LENS_USER_AGENT = "Rock-Lens/0.1"
ALLOWED_ENDPOINTS = frozenset(
    {
        "/api/People",
        "/api/Groups",
        "/api/WorkflowTypes",
        "/api/ServiceJobs",
        "/api/Pages",
        "/api/ContentChannelItems",
        "/api/PersonalLinks/GetPersonalLinksData",
    }
)
ALLOWED_ODATA_PARAMETERS = frozenset(
    {"$expand", "$filter", "$select", "$orderby", "$top"}
)


class RockRestError(Exception):
    """A stable REST error that never includes a cookie, URL, or response body."""


class CookieProvider(Protocol):
    def authenticated_cookie(self) -> AbstractContextManager[str]: ...


class JsonClient(Protocol):
    def get_json(self, path: str, params: dict[str, str], cookie: str) -> Any: ...


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


class RockRestHttpClient:
    """Fixed-origin, GET-only Rock REST client."""

    def __init__(
        self, opener: Any | None = None, origin: str = DEFAULT_ROCK_ORIGIN
    ) -> None:
        # Injected openers are retained for deterministic tests. Production calls
        # create one opener per request so fixed endpoint reads can run safely in
        # parallel without sharing urllib handler state between threads.
        self._opener = opener
        self.origin = validate_rock_origin(origin)

    def set_origin(self, origin: str) -> None:
        self.origin = validate_rock_origin(origin)

    def get_json(self, path: str, params: dict[str, str], cookie: str) -> Any:
        if path not in ALLOWED_ENDPOINTS:
            raise RockRestError("rock_endpoint_not_allowed")
        if (
            not isinstance(params, dict)
            or not set(params).issubset(ALLOWED_ODATA_PARAMETERS)
            or any(
                not isinstance(value, str) or len(value) > 2_000
                for value in params.values()
            )
        ):
            raise RockRestError("rock_query_not_allowed")
        if path == "/api/PersonalLinks/GetPersonalLinksData" and params:
            raise RockRestError("rock_query_not_allowed")
        if (
            not isinstance(cookie, str)
            or not cookie.startswith(".ROCK=")
            or len(cookie) > 16 * 1024
            or any(ord(char) < 33 or char in ';,\\"' for char in cookie)
        ):
            raise RockRestError("invalid_rock_cookie")

        query = urllib.parse.urlencode(params)
        url = self.origin + path + ("?" + query if query else "")
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Cookie": cookie,
                "User-Agent": ROCK_LENS_USER_AGENT,
            },
            method="GET",
        )
        try:
            opener = self._opener or urllib.request.build_opener(_RejectRedirects())
            with opener.open(request, timeout=20) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except (OSError, urllib.error.URLError, urllib.error.HTTPError) as error:
            raise RockRestError("rock_request_failed") from error
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RockRestError("rock_response_out_of_bounds")
        try:
            return json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RockRestError("invalid_rock_response") from error


@dataclass(frozen=True)
class _SearchSpec:
    category: str
    navigation_kind: str
    path: str
    search_fields: tuple[str, ...]
    select: str
    order_by: str
    title_fields: tuple[str, ...]
    subtitle: str
    type_order: int
    route: str | None = None
    active_field: str | None = None
    status_field: str | None = None
    expand: str | None = None


@dataclass(frozen=True)
class SearchBatch:
    results: list[dict[str, Any]]
    unavailable: tuple[str, ...]


@dataclass(frozen=True)
class _RegistryEntry:
    target: NavigationTarget | None
    person: dict[str, Any] | None


SEARCH_SPECS = (
    _SearchSpec(
        "People",
        "Person",
        "/api/People",
        ("NickName", "LastName"),
        "Id,NickName,LastName",
        "LastName,NickName",
        ("NickName", "LastName"),
        "Person · live Rock record",
        10,
        "/Person/{id}",
    ),
    _SearchSpec(
        "Groups",
        "Group",
        "/api/Groups",
        ("Name",),
        "Id,Name,IsActive,GroupType/Name",
        "Name",
        ("Name",),
        "Group",
        20,
        "/Group/{id}",
        active_field="IsActive",
        expand="GroupType",
    ),
    _SearchSpec(
        "Workflows",
        "Workflow Type",
        "/api/WorkflowTypes",
        ("Name",),
        "Id,Name,IsActive",
        "Name",
        ("Name",),
        "Workflow type",
        30,
        "/admin/general/workflows?WorkflowTypeId={id}",
        active_field="IsActive",
    ),
    _SearchSpec(
        "Jobs",
        "Scheduled Job",
        "/api/ServiceJobs",
        ("Name",),
        "Id,Name,IsActive,LastStatus",
        "Name",
        ("Name",),
        "Service job",
        40,
        "/admin/system/jobs/{id}",
        active_field="IsActive",
        status_field="LastStatus",
    ),
    _SearchSpec(
        "Pages",
        "Page",
        "/api/Pages",
        ("PageTitle", "InternalName"),
        "Id,PageTitle,InternalName",
        "PageTitle",
        ("PageTitle", "InternalName"),
        "Internal page",
        50,
        "/page/{id}",
    ),
    _SearchSpec(
        "Content Channel Items",
        "Content Channel Item",
        "/api/ContentChannelItems",
        ("Title",),
        "Id,Title,Status",
        "Title",
        ("Title",),
        "Content channel item",
        60,
        "/ContentChannelItem/{id}",
        status_field="Status",
    ),
)


class RockRestReadOnlyAdapter:
    """Typed, allowlisted Rock reads backed by Magnus' ephemeral session cookie."""

    def __init__(
        self,
        cookie_provider: CookieProvider,
        http: JsonClient | None = None,
        origin: str = DEFAULT_ROCK_ORIGIN,
    ) -> None:
        self._cookie_provider = cookie_provider
        self.origin = validate_rock_origin(origin)
        self._http = http or RockRestHttpClient(origin=self.origin)
        self._key = secrets.token_bytes(32)
        self._registry: OrderedDict[str, _RegistryEntry] = OrderedDict()

    def set_origin(self, origin: str) -> None:
        try:
            self.origin = validate_rock_origin(origin)
        except OriginError as error:
            raise RockRestError("invalid_rock_origin") from error
        setter = getattr(self._http, "set_origin", None)
        if callable(setter):
            setter(self.origin)
        self.clear()

    def clear(self) -> None:
        self._registry.clear()

    def search(self, query: str, category: str | None = None) -> SearchBatch:
        normalized = sanitize_text(query, 120)
        specs = (
            SEARCH_SPECS
            if category is None
            else tuple(spec for spec in SEARCH_SPECS if spec.category == category)
        )
        if not specs:
            raise RockRestError("invalid_search_scope")
        if not normalized and category is None:
            return SearchBatch([], ())

        results: list[dict[str, Any]] = []
        unavailable: list[str] = []
        try:
            with (
                self._cookie_provider.authenticated_cookie() as cookie,
                ThreadPoolExecutor(
                    max_workers=len(specs),
                    thread_name_prefix="rock-lens-rest",
                ) as executor,
            ):
                requests = [
                    executor.submit(
                        self._http.get_json,
                        spec.path,
                        self._params(spec, normalized),
                        cookie,
                    )
                    for spec in specs
                ]
                # Consume in the fixed category order so presentation and
                # partial-failure reporting remain deterministic.
                for spec, request in zip(specs, requests, strict=True):
                    try:
                        value = request.result()
                        results.extend(self._transform_rows(spec, value))
                    except RockRestError:
                        unavailable.append(spec.category)
        except MagnusError as error:
            raise RockRestError("rock_login_failed") from error

        if len(unavailable) == len(specs):
            self._invalidate_cookie()
            raise RockRestError("rock_search_failed")
        return SearchBatch(results, tuple(unavailable))

    def personal_links(self) -> list[dict[str, Any]]:
        try:
            with self._cookie_provider.authenticated_cookie() as cookie:
                value = self._http.get_json(
                    "/api/PersonalLinks/GetPersonalLinksData", {}, cookie
                )
        except MagnusError as error:
            raise RockRestError("rock_login_failed") from error
        except RockRestError:
            self._invalidate_cookie()
            raise
        if not isinstance(value, dict):
            raise RockRestError("invalid_rock_response")
        sections = self._field(value, "PersonLinksSectionList")
        if not isinstance(sections, list):
            raise RockRestError("invalid_rock_response")

        flattened: list[tuple[int, int, dict[str, Any]]] = []
        seen = 0
        for section in sections[:50]:
            if not isinstance(section, dict):
                continue
            section_name = sanitize_text(self._field(section, "Name"), 120)
            section_order = self._integer(self._field(section, "Order"), 0)
            shared = bool(self._field(section, "IsShared"))
            links = self._field(section, "PersonalLinks")
            if not section_name or not isinstance(links, list):
                continue
            for link in links:
                if seen >= MAX_PERSONAL_LINKS:
                    break
                seen += 1
                if not isinstance(link, dict):
                    continue
                title = sanitize_text(self._field(link, "Name"), 160)
                raw_url = self._field(link, "Url")
                if not title or not isinstance(raw_url, str):
                    continue
                try:
                    target = clean_target(
                        title, "Personal Link", 90, raw_url, self.origin
                    )
                except NavigationError:
                    continue
                safe_id = self._register("Personal Link", raw_url, target, None)
                public = allowlist(
                    {
                        "safeId": safe_id,
                        "title": title,
                        "section": section_name,
                        "isShared": shared,
                    },
                    ALLOWED_LINK_KEYS,
                )
                link_order = self._integer(self._field(link, "Order"), 0)
                flattened.append((section_order, link_order, public))
        flattened.sort(key=lambda item: (item[0], item[1], item[2]["title"]))
        return [item[2] for item in flattened]

    def resolve(self, safe_id: str) -> NavigationTarget | None:
        entry = self._registry.get(sanitize_text(safe_id, 100))
        return entry.target if entry else None

    def person_quick_look(self, safe_id: str) -> dict[str, Any] | None:
        entry = self._registry.get(sanitize_text(safe_id, 100))
        if not entry or not entry.person:
            return None
        return allowlist(dict(entry.person), ALLOWED_PERSON_KEYS)

    def _params(self, spec: _SearchSpec, query: str) -> dict[str, str]:
        tokens = (
            query.split() if spec.category == "People" else ([query] if query else [])
        )
        clauses: list[str] = []
        for token in tokens:
            escaped = token.replace("'", "''")
            alternatives = [
                f"startswith({field},'{escaped}')" for field in spec.search_fields
            ]
            clauses.append(
                alternatives[0]
                if len(alternatives) == 1
                else "(" + " or ".join(alternatives) + ")"
            )
        params = {
            "$select": spec.select,
            "$orderby": spec.order_by,
            "$top": str(ROWS_PER_CATEGORY),
        }
        if clauses:
            params["$filter"] = " and ".join(clauses)
        if spec.expand:
            params["$expand"] = spec.expand
        return params

    def _transform_rows(self, spec: _SearchSpec, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list) or len(value) > 1_000:
            raise RockRestError("invalid_rock_response")
        results: list[dict[str, Any]] = []
        for row in value[:ROWS_PER_CATEGORY]:
            if not isinstance(row, dict):
                continue
            raw_id = self._positive_id(self._field(row, "Id"))
            title_parts = [
                sanitize_text(self._field(row, field), 100)
                for field in spec.title_fields
            ]
            title = (
                " ".join(part for part in title_parts if part)
                if spec.category == "People"
                else next((part for part in title_parts if part), "")
            )
            if not raw_id or not title:
                continue
            status = self._status(spec, row)
            subtitle = spec.subtitle
            if spec.category == "Groups":
                group_type = self._field(row, "GroupType")
                if isinstance(group_type, dict):
                    group_type_name = sanitize_text(
                        self._field(group_type, "Name"), 100
                    )
                    if group_type_name:
                        subtitle = group_type_name
            target: NavigationTarget | None = None
            if spec.route:
                try:
                    target = clean_target(
                        title,
                        spec.navigation_kind,
                        spec.type_order,
                        spec.route.format(id=raw_id),
                        self.origin,
                    )
                except NavigationError:
                    target = None
            person = None
            if spec.category == "People":
                person = {
                    "safeId": "",
                    "displayName": title,
                    "subtitle": "Live Rock record · read-only",
                    "campus": "Not requested",
                }
            safe_id = self._register(spec.category, raw_id, target, person)
            if person is not None:
                person["safeId"] = safe_id
            results.append(
                allowlist(
                    {
                        "category": spec.category,
                        "safeId": safe_id,
                        "title": title,
                        "subtitle": subtitle,
                        "status": status,
                        "canOpen": target is not None,
                    },
                    ALLOWED_RESULT_KEYS,
                )
            )
        return results

    def _register(
        self,
        namespace: str,
        identity: str,
        target: NavigationTarget | None,
        person: dict[str, Any] | None,
    ) -> str:
        message = f"{namespace}\0{identity}".encode()
        safe_id = (
            "rock-" + hmac.new(self._key, message, hashlib.sha256).hexdigest()[:32]
        )
        self._registry[safe_id] = _RegistryEntry(target, person)
        self._registry.move_to_end(safe_id)
        while len(self._registry) > MAX_TARGETS:
            self._registry.popitem(last=False)
        return safe_id

    def _invalidate_cookie(self) -> None:
        invalidator = getattr(
            self._cookie_provider, "invalidate_authenticated_cookie", None
        )
        if callable(invalidator):
            invalidator()

    @classmethod
    def _field(cls, record: dict[str, Any], name: str) -> Any:
        if name in record:
            return record[name]
        return record.get(name[0].lower() + name[1:])

    @staticmethod
    def _positive_id(value: Any) -> str:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return ""
        return str(number) if number > 0 else ""

    @staticmethod
    def _integer(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _status(cls, spec: _SearchSpec, row: dict[str, Any]) -> str:
        if spec.status_field:
            value = sanitize_text(cls._field(row, spec.status_field), 80)
            if value:
                return value
        if spec.active_field:
            value = cls._field(row, spec.active_field)
            if isinstance(value, bool):
                return "Active" if value else "Inactive"
        return "Live"

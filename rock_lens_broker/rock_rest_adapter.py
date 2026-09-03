from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
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
from .http_security import (
    HttpSecurityError,
    decode_bounded_json,
    redirect_free_opener,
    validate_rock_cookie_header,
)
from .navigation import NavigationError, NavigationTarget, clean_target
from .origin import DEFAULT_ROCK_ORIGIN, OriginError, validate_rock_origin
from .rock_session import RockSessionError
from .version import HTTP_USER_AGENT

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_TARGETS = 256
MAX_PERSONAL_LINKS = 200
PERSONAL_LINK_CACHE_SECONDS = 5 * 60
SEARCH_CAPABILITY_CACHE_SECONDS = 5 * 60
ROWS_PER_CATEGORY = 3
ROCK_ARCH_USER_AGENT = HTTP_USER_AGENT
GUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
ALLOWED_ENDPOINTS = frozenset(
    {
        "/api/People",
        "/api/Groups",
        "/api/GroupTypes",
        "/api/WorkflowTypes",
        "/api/ServiceJobs",
        "/api/Pages",
        "/api/ContentChannelTypes",
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
        try:
            safe_cookie = validate_rock_cookie_header(cookie)
        except HttpSecurityError as error:
            raise RockRestError("invalid_rock_cookie") from error

        query = urllib.parse.urlencode(params)
        url = self.origin + path + ("?" + query if query else "")
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Cookie": safe_cookie,
                "User-Agent": ROCK_ARCH_USER_AGENT,
            },
            method="GET",
        )
        try:
            opener = redirect_free_opener(self._opener)
            with opener.open(request, timeout=20) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
            if status in {401, 403, 404}:
                raise RockRestError("rock_endpoint_unavailable") from error
            raise RockRestError("rock_request_failed") from error
        except (OSError, urllib.error.URLError) as error:
            raise RockRestError("rock_request_failed") from error
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RockRestError("rock_response_out_of_bounds")
        try:
            return decode_bounded_json(raw)
        except HttpSecurityError as error:
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
class SearchCapabilities:
    available: tuple[str, ...]
    unavailable: tuple[str, ...]


@dataclass(frozen=True)
class _RegistryEntry:
    target: NavigationTarget | None
    person: dict[str, Any] | None


@dataclass(frozen=True)
class _FamilyContext:
    campus: str
    adults: tuple[tuple[str, str], ...]


SEARCH_SPECS = (
    _SearchSpec(
        "People",
        "Person",
        "/api/People",
        ("NickName", "LastName"),
        (
            "Id,NickName,LastName,Age,GivingGroupId,"
            "MaritalStatusValue/Value,ConnectionStatusValue/Value,"
            "RecordStatusValue/Value"
        ),
        "LastName,NickName",
        ("NickName", "LastName"),
        "Person",
        10,
        "/Person/{id}",
        expand="MaritalStatusValue,ConnectionStatusValue,RecordStatusValue",
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
        "Group Types",
        "Group Type",
        "/api/GroupTypes",
        ("Name",),
        "Id,Name",
        "Name",
        ("Name",),
        "Group type",
        25,
        "/admin/general/group-types?GroupTypeId={id}",
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
        "Content Channel Types",
        "Content Channel Type",
        "/api/ContentChannelTypes",
        ("Name",),
        "Id,Name",
        "Name",
        ("Name",),
        "Content channel type",
        55,
        "/admin/cms/content-channel-type?ContentChannelTypeId={id}",
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
    """Typed, allowlisted Rock reads backed by the native Rock session cookie."""

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
        self._family_contexts: OrderedDict[str, _FamilyContext] = OrderedDict()
        self._personal_links_cache: list[dict[str, Any]] = []
        self._personal_links_cache_deadline = 0.0
        self._personal_links_loaded = False
        self._search_capabilities = SearchCapabilities((), ())
        self._search_capabilities_deadline = 0.0
        self._search_capabilities_loaded = False

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
        self._family_contexts.clear()
        self._personal_links_cache = []
        self._personal_links_cache_deadline = 0.0
        self._personal_links_loaded = False
        self._search_capabilities = SearchCapabilities((), ())
        self._search_capabilities_deadline = 0.0
        self._search_capabilities_loaded = False

    def searchable_categories(
        self, force_refresh: bool = False
    ) -> SearchCapabilities:
        if (
            not force_refresh
            and self._search_capabilities_loaded
            and time.monotonic() < self._search_capabilities_deadline
        ):
            return self._search_capabilities

        available: list[str] = []
        unavailable: list[str] = []
        transient_failure = False
        try:
            with (
                self._cookie_provider.authenticated_cookie() as cookie,
                ThreadPoolExecutor(
                    max_workers=len(SEARCH_SPECS),
                    thread_name_prefix="rock-arch-access",
                ) as executor,
            ):
                requests = [
                    executor.submit(
                        self._http.get_json,
                        spec.path,
                        {"$select": "Id", "$top": "1"},
                        cookie,
                    )
                    for spec in SEARCH_SPECS
                ]
                for spec, request in zip(SEARCH_SPECS, requests, strict=True):
                    try:
                        value = request.result()
                        if not isinstance(value, list) or len(value) > 1_000:
                            raise RockRestError("invalid_rock_response")
                        available.append(spec.category)
                    except RockRestError as error:
                        if str(error) == "rock_endpoint_unavailable":
                            unavailable.append(spec.category)
                        else:
                            transient_failure = True
        except RockSessionError as error:
            raise RockRestError("rock_login_failed") from error

        if transient_failure:
            if self._search_capabilities_loaded:
                return self._search_capabilities
            raise RockRestError("rock_capability_check_failed")

        self._search_capabilities = SearchCapabilities(
            tuple(available), tuple(unavailable)
        )
        self._search_capabilities_deadline = (
            time.monotonic() + SEARCH_CAPABILITY_CACHE_SECONDS
        )
        self._search_capabilities_loaded = True
        return self._search_capabilities

    def search(
        self,
        query: str,
        category: str | None = None,
        categories: list[str] | None = None,
        include_person_context: bool = True,
    ) -> SearchBatch:
        normalized = sanitize_text(query, 120)
        known_categories = {spec.category for spec in SEARCH_SPECS}
        if category is not None and category not in known_categories:
            raise RockRestError("invalid_search_scope")
        enabled = set(categories) if categories is not None else {
            spec.category for spec in SEARCH_SPECS
        }
        specs = (
            tuple(spec for spec in SEARCH_SPECS if spec.category in enabled)
            if category is None
            else tuple(
                spec
                for spec in SEARCH_SPECS
                if spec.category == category and spec.category in enabled
            )
        )
        if not specs:
            return SearchBatch([], ())
        if not normalized and category is None:
            return SearchBatch([], ())

        results: list[dict[str, Any]] = []
        unavailable: list[str] = []
        try:
            with (
                self._cookie_provider.authenticated_cookie() as cookie,
                ThreadPoolExecutor(
                    max_workers=len(specs),
                    thread_name_prefix="rock-arch-rest",
                ) as executor,
            ):
                requests = [
                    executor.submit(
                        self._http.get_json,
                        spec.path,
                        self._params(
                            spec,
                            normalized,
                            include_person_context,
                            allow_numeric_id=True,
                        ),
                        cookie,
                    )
                    for spec in specs
                ]
                # Consume in the fixed category order so presentation and
                # partial-failure reporting remain deterministic.
                for spec, request in zip(specs, requests, strict=True):
                    try:
                        value = request.result()
                        family_contexts = (
                            self._load_family_contexts(value, cookie)
                            if spec.category == "People" and include_person_context
                            else {}
                        )
                        results.extend(
                            self._transform_rows(
                                spec,
                                value,
                                family_contexts,
                                include_person_context,
                            )
                        )
                    except RockRestError:
                        unavailable.append(spec.category)
        except RockSessionError as error:
            raise RockRestError("rock_login_failed") from error

        if len(unavailable) == len(specs):
            self._invalidate_cookie()
            raise RockRestError("rock_search_failed")
        return SearchBatch(results, tuple(unavailable))

    def personal_links(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        if (
            not force_refresh
            and self._personal_links_loaded
            and time.monotonic() < self._personal_links_cache_deadline
        ):
            return [dict(item) for item in self._personal_links_cache]
        try:
            with self._cookie_provider.authenticated_cookie() as cookie:
                value = self._http.get_json(
                    "/api/PersonalLinks/GetPersonalLinksData", {}, cookie
                )
        except RockSessionError as error:
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
        result = [item[2] for item in flattened]
        self._personal_links_cache = [dict(item) for item in result]
        self._personal_links_cache_deadline = (
            time.monotonic() + PERSONAL_LINK_CACHE_SECONDS
        )
        self._personal_links_loaded = True
        return result

    def resolve(self, safe_id: str) -> NavigationTarget | None:
        entry = self._registry.get(sanitize_text(safe_id, 100))
        return entry.target if entry else None

    def person_quick_look(self, safe_id: str) -> dict[str, Any] | None:
        entry = self._registry.get(sanitize_text(safe_id, 100))
        if not entry or not entry.person:
            return None
        return allowlist(dict(entry.person), ALLOWED_PERSON_KEYS)

    def _params(
        self,
        spec: _SearchSpec,
        query: str,
        include_person_context: bool = True,
        allow_numeric_id: bool = False,
    ) -> dict[str, str]:
        identity_filter = self._identity_filter(query, allow_numeric_id)
        clauses: list[str] = []
        if identity_filter:
            clauses.append(identity_filter)
        else:
            tokens = (
                query.split()
                if spec.category == "People"
                else ([query] if query else [])
            )
            for token in tokens:
                escaped = token.replace("'", "''")
                alternatives = [
                    f"startswith({field},'{escaped}')"
                    for field in spec.search_fields
                ]
                clauses.append(
                    alternatives[0]
                    if len(alternatives) == 1
                    else "(" + " or ".join(alternatives) + ")"
                )
        people_without_context = (
            spec.category == "People" and not include_person_context
        )
        params = {
            "$select": (
                "Id,NickName,LastName" if people_without_context else spec.select
            ),
            "$orderby": spec.order_by,
            "$top": str(ROWS_PER_CATEGORY),
        }
        if clauses:
            params["$filter"] = " and ".join(clauses)
        if spec.expand and not people_without_context:
            params["$expand"] = spec.expand
        return params

    @staticmethod
    def _identity_filter(query: str, allow_numeric_id: bool) -> str:
        if allow_numeric_id and query.isdigit() and int(query) > 0:
            return f"Id eq {int(query)}"
        if GUID_PATTERN.fullmatch(query):
            return f"Guid eq guid'{query.lower()}'"
        return ""

    def _transform_rows(
        self,
        spec: _SearchSpec,
        value: Any,
        family_contexts: dict[str, _FamilyContext] | None = None,
        include_person_context: bool = True,
    ) -> list[dict[str, Any]]:
        if not isinstance(value, list) or len(value) > 1_000:
            raise RockRestError("invalid_rock_response")
        family_contexts = family_contexts or {}
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
            person_quick_subtitle = "Live Rock record · read-only"
            person_campus = "Campus not available"
            if spec.category == "People" and include_person_context:
                family_id = self._positive_id(self._field(row, "GivingGroupId"))
                family = family_contexts.get(family_id)
                identity_parts: list[str] = []
                age = self._age(self._field(row, "Age"))
                if age is not None:
                    identity_parts.append(f"Age {age}")
                spouse = self._spouse_name(raw_id, row, family)
                if spouse:
                    identity_parts.append(f"Spouse {spouse}")
                if family and family.campus:
                    person_campus = f"Campus · {family.campus}"
                search_parts = list(identity_parts)
                if family and family.campus:
                    search_parts.append(family.campus)
                subtitle = " · ".join(search_parts) or spec.subtitle
                status = self._person_status(row)
                quick_parts = identity_parts + ([status] if status else [])
                person_quick_subtitle = (
                    " · ".join(quick_parts) or "Live Rock record · read-only"
                )
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
                    "subtitle": person_quick_subtitle,
                    "campus": person_campus,
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

    def _load_family_contexts(
        self, people: Any, cookie: str
    ) -> dict[str, _FamilyContext]:
        if not isinstance(people, list):
            return {}
        family_ids: list[str] = []
        for row in people[:ROWS_PER_CATEGORY]:
            if not isinstance(row, dict):
                continue
            family_id = self._positive_id(self._field(row, "GivingGroupId"))
            if family_id and family_id not in family_ids:
                family_ids.append(family_id)

        contexts: dict[str, _FamilyContext] = {}
        missing: list[str] = []
        for family_id in family_ids:
            cached = self._family_contexts.get(family_id)
            if cached is None:
                missing.append(family_id)
                continue
            self._family_contexts.move_to_end(family_id)
            contexts[family_id] = cached
        if not missing:
            return contexts

        family_filter = " or ".join(f"Id eq {family_id}" for family_id in missing)
        if len(missing) > 1:
            family_filter = f"({family_filter})"
        try:
            value = self._http.get_json(
                "/api/Groups",
                {
                    "$filter": family_filter,
                    "$select": (
                        "Id,Campus/Name,Members/PersonId,Members/IsArchived,"
                        "Members/Person/NickName,Members/Person/LastName,"
                        "Members/GroupRole/Name"
                    ),
                    "$expand": "Campus,Members,Members/Person,Members/GroupRole",
                    "$orderby": "Id",
                    "$top": str(len(missing)),
                },
                cookie,
            )
        except RockRestError:
            return contexts
        if not isinstance(value, list) or len(value) > ROWS_PER_CATEGORY:
            return contexts

        loaded: dict[str, _FamilyContext] = {}
        for group in value:
            if not isinstance(group, dict):
                continue
            family_id = self._positive_id(self._field(group, "Id"))
            if family_id not in missing:
                continue
            loaded[family_id] = self._family_context(group)
        for family_id in missing:
            context = loaded.get(family_id, _FamilyContext("", ()))
            self._family_contexts[family_id] = context
            self._family_contexts.move_to_end(family_id)
            contexts[family_id] = context
        while len(self._family_contexts) > MAX_TARGETS:
            self._family_contexts.popitem(last=False)
        return contexts

    @classmethod
    def _family_context(cls, group: dict[str, Any]) -> _FamilyContext:
        campus_record = cls._field(group, "Campus")
        campus = (
            sanitize_text(cls._field(campus_record, "Name"), 80)
            if isinstance(campus_record, dict)
            else ""
        )
        adults: list[tuple[str, str]] = []
        seen: set[str] = set()
        members = cls._field(group, "Members")
        if not isinstance(members, list):
            return _FamilyContext(campus, ())
        for member in members[:50]:
            if not isinstance(member, dict) or cls._field(member, "IsArchived") is True:
                continue
            role = cls._field(member, "GroupRole")
            role_name = (
                sanitize_text(cls._field(role, "Name"), 40)
                if isinstance(role, dict)
                else ""
            )
            if role_name.casefold() != "adult":
                continue
            person = cls._field(member, "Person")
            if not isinstance(person, dict):
                continue
            person_id = cls._positive_id(cls._field(member, "PersonId"))
            name = " ".join(
                part
                for part in (
                    sanitize_text(cls._field(person, "NickName"), 60),
                    sanitize_text(cls._field(person, "LastName"), 60),
                )
                if part
            )
            if person_id and name and person_id not in seen:
                seen.add(person_id)
                adults.append((person_id, name))
        return _FamilyContext(campus, tuple(adults))

    @classmethod
    def _spouse_name(
        cls,
        person_id: str,
        row: dict[str, Any],
        family: _FamilyContext | None,
    ) -> str:
        if not family:
            return ""
        marital = cls._defined_value(row, "MaritalStatusValue")
        if marital.casefold() != "married":
            return ""
        candidates = [
            name for member_id, name in family.adults if member_id != person_id
        ]
        return candidates[0] if len(candidates) == 1 else ""

    @classmethod
    def _person_status(cls, row: dict[str, Any]) -> str:
        record_status = cls._defined_value(row, "RecordStatusValue")
        if record_status and record_status.casefold() != "active":
            return record_status
        return (
            cls._defined_value(row, "ConnectionStatusValue") or record_status or "Live"
        )

    @classmethod
    def _defined_value(cls, row: dict[str, Any], name: str) -> str:
        value = cls._field(row, name)
        return (
            sanitize_text(cls._field(value, "Value"), 80)
            if isinstance(value, dict)
            else ""
        )

    @staticmethod
    def _age(value: Any) -> int | None:
        try:
            age = int(value)
        except (TypeError, ValueError):
            return None
        return age if 0 <= age <= 125 else None

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

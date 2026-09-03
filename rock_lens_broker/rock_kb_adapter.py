from __future__ import annotations

import hashlib
import hmac
import ipaddress
import secrets
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Protocol

from .contracts import ALLOWED_RESULT_KEYS, allowlist, sanitize_text
from .http_security import HttpSecurityError, decode_bounded_json, redirect_free_opener
from .version import HTTP_USER_AGENT

ROCK_KB_ORIGIN = "https://rock-agent-kb.oneandall.church"
ROCK_KB_ATTRIBUTION = "Rock Agent Knowledge Base · ONE&ALL Church"
SEARCH_RESPONSE_LIMIT = 512 * 1024
DETAIL_RESPONSE_LIMIT = 2 * 1024 * 1024
HTTP_TIMEOUT_SECONDS = 8
SEARCH_RESULT_LIMIT = 10
CACHE_SECONDS = 5 * 60
MAX_REGISTERED_RESULTS = 256
MAX_CACHED_SEARCHES = 40
MAX_RESULT_ID_LENGTH = 500
MAX_BODY_LENGTH = 20_000

KIND_LABELS = {
    "claim": "Claim",
    "community_contribution": "Community contribution",
    "concept": "Guide",
    "guide_section": "Guide",
    "lava_context": "Lava context",
    "model_map": "Model Map",
    "recipe": "Recipe",
    "rock_idea": "Rock idea",
    "rock_issue": "Rock issue",
    "source_summary": "Source summary",
    "structured_reference": "Reference",
    "task_card": "Task card",
    "troubleshooting_node": "Troubleshooting",
}

TRUST_LABELS = {
    "live_verified": "Live verified",
    "official": "Official",
    "release-note-confirmed": "Release note confirmed",
    "rocku-confirmed": "RockU confirmed",
    "source-code-confirmed": "Source confirmed",
    "community-reviewed": "Community reviewed",
    "community-unreviewed": "Community report · unreviewed",
}


class RockKbError(Exception):
    """A stable public-KB error that never includes a query or response body."""


class RockKbHttp(Protocol):
    def search(self, query: str, limit: int = SEARCH_RESULT_LIMIT) -> Any: ...

    def result(self, result_id: str) -> Any: ...


class RockKbHttpClient:
    """Fixed-origin, redirect-free, credentialless client for the public KB."""

    def __init__(self, opener: Any | None = None) -> None:
        self._opener = opener

    def search(self, query: str, limit: int = SEARCH_RESULT_LIMIT) -> Any:
        normalized = sanitize_text(query, 120)
        if len(normalized) < 3 or not 1 <= limit <= SEARCH_RESULT_LIMIT:
            raise RockKbError("invalid_knowledge_query")
        return self._get_json(
            "/search",
            {
                "q": normalized,
                "limit": str(limit),
                "min_claim_tier": "source_backed",
                "detail": "compact",
            },
            SEARCH_RESPONSE_LIMIT,
        )

    def result(self, result_id: str) -> Any:
        safe_id = _validate_result_id(result_id)
        return self._get_json(
            "/results/" + urllib.parse.quote(safe_id, safe=""),
            {},
            DETAIL_RESPONSE_LIMIT,
        )

    def _get_json(
        self, path: str, params: dict[str, str], maximum: int
    ) -> Any:
        if path != "/search" and not path.startswith("/results/"):
            raise RockKbError("knowledge_endpoint_not_allowed")
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(
            ROCK_KB_ORIGIN + path + ("?" + query if query else ""),
            headers={
                "Accept": "application/json",
                "User-Agent": HTTP_USER_AGENT,
            },
            method="GET",
        )
        try:
            opener = redirect_free_opener(self._opener)
            with opener.open(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                raw = response.read(maximum + 1)
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
            if status == 404:
                raise RockKbError("knowledge_result_not_found") from error
            raise RockKbError("knowledge_unavailable") from error
        except (OSError, urllib.error.URLError) as error:
            raise RockKbError("knowledge_unavailable") from error
        if len(raw) > maximum:
            raise RockKbError("knowledge_response_out_of_bounds")
        try:
            return decode_bounded_json(raw)
        except HttpSecurityError as error:
            raise RockKbError("invalid_knowledge_response") from error


@dataclass(frozen=True)
class _KnowledgeEntry:
    result_id: str
    source_url: str


class RockKbReadOnlyAdapter:
    """Transforms public KB records into Rock Arch's minimal display contract."""

    def __init__(self, http: RockKbHttp | None = None) -> None:
        self._http = http or RockKbHttpClient()
        self._key = secrets.token_bytes(32)
        self._registry: OrderedDict[str, _KnowledgeEntry] = OrderedDict()
        self._search_cache: OrderedDict[
            str, tuple[float, list[dict[str, Any]]]
        ] = OrderedDict()
        self._detail_cache: OrderedDict[
            str, tuple[float, dict[str, Any]]
        ] = OrderedDict()

    def search(self, query: str) -> list[dict[str, Any]]:
        normalized = sanitize_text(query, 120)
        if len(normalized) < 3:
            return []
        cache_key = normalized.casefold()
        cached = self._cached(self._search_cache, cache_key)
        if isinstance(cached, list):
            return [dict(item) for item in cached]

        payload = self._http.search(normalized, SEARCH_RESULT_LIMIT)
        if (
            not isinstance(payload, dict)
            or payload.get("schema") != "rock-kb-search-result-v3"
            or not isinstance(payload.get("results"), list)
            or len(payload["results"]) > 50
        ):
            raise RockKbError("invalid_knowledge_response")

        results: list[dict[str, Any]] = []
        for row in payload["results"][:SEARCH_RESULT_LIMIT]:
            public = self._search_result(row)
            if public:
                results.append(public)
        self._cache(self._search_cache, cache_key, results, MAX_CACHED_SEARCHES)
        return [dict(item) for item in results]

    def detail(self, safe_id: str) -> dict[str, Any]:
        public_id = sanitize_text(safe_id, 100)
        entry = self._registry.get(public_id)
        if not entry:
            raise RockKbError("knowledge_result_not_found")
        self._registry.move_to_end(public_id)

        cached = self._cached(self._detail_cache, public_id)
        if isinstance(cached, dict):
            return dict(cached)

        payload = self._http.result(entry.result_id)
        if (
            not isinstance(payload, dict)
            or payload.get("schema") != "rock-kb-result-v1"
            or payload.get("status") != "ok"
            or payload.get("requested_result_id") != entry.result_id
            or not isinstance(payload.get("result"), dict)
        ):
            raise RockKbError("invalid_knowledge_response")
        row = payload["result"]
        canonical_id = _validate_result_id(payload.get("canonical_result_id"))
        if _validate_result_id(row.get("id")) != canonical_id:
            raise RockKbError("invalid_knowledge_response")

        title = sanitize_text(row.get("title"), 160)
        body = _sanitize_body(row.get("body"), MAX_BODY_LENGTH)
        if not title or not body:
            raise RockKbError("invalid_knowledge_response")
        kind = _kind(row.get("kind"))
        authority = sanitize_text(row.get("authority_tier"), 60)
        claim_tier = sanitize_text(row.get("claim_tier"), 60)
        source_url = _first_source_url(row)
        self._registry[public_id] = _KnowledgeEntry(entry.result_id, source_url)
        self._registry.move_to_end(public_id)

        detail = {
            "safeId": public_id,
            "title": title,
            "kind": KIND_LABELS.get(kind, "Knowledge"),
            "body": body,
            "trust": TRUST_LABELS.get(authority, _humanize(authority) or "Public knowledge"),
            "claimTier": _humanize(claim_tier) or "Claim tier not specified",
            "version": _version_label(row),
            "sourceHost": _source_host(source_url),
            "canOpenSource": bool(source_url),
            "attribution": ROCK_KB_ATTRIBUTION,
        }
        self._cache(self._detail_cache, public_id, detail, MAX_REGISTERED_RESULTS)
        return dict(detail)

    def source_url(self, safe_id: str) -> str | None:
        entry = self._registry.get(sanitize_text(safe_id, 100))
        return entry.source_url if entry and entry.source_url else None

    def _search_result(self, row: Any) -> dict[str, Any] | None:
        if not isinstance(row, dict):
            return None
        try:
            result_id = _validate_result_id(row.get("id"))
        except RockKbError:
            return None
        title = sanitize_text(row.get("title"), 160)
        if not title:
            return None
        kind = _kind(row.get("kind"))
        snippet = _snippet(row.get("snippet"))
        authority = sanitize_text(row.get("authority_tier"), 60)
        source_url = _safe_source_url(row.get("url"))
        safe_id = self._register(result_id, source_url)
        return allowlist(
            {
                "category": "Knowledge",
                "safeId": safe_id,
                "title": title,
                "subtitle": snippet or KIND_LABELS.get(kind, "Public Rock knowledge"),
                "status": TRUST_LABELS.get(
                    authority, _humanize(authority) or "Public knowledge"
                ),
                "canOpen": True,
            },
            ALLOWED_RESULT_KEYS,
        )

    def _register(self, result_id: str, source_url: str) -> str:
        digest = hmac.new(
            self._key, ("rock-kb\0" + result_id).encode(), hashlib.sha256
        ).hexdigest()[:32]
        safe_id = "kb-" + digest
        self._registry[safe_id] = _KnowledgeEntry(result_id, source_url)
        self._registry.move_to_end(safe_id)
        while len(self._registry) > MAX_REGISTERED_RESULTS:
            evicted, _ = self._registry.popitem(last=False)
            self._detail_cache.pop(evicted, None)
        return safe_id

    @staticmethod
    def _cached(cache: OrderedDict[str, tuple[float, Any]], key: str) -> Any | None:
        item = cache.get(key)
        if not item:
            return None
        deadline, value = item
        if time.monotonic() >= deadline:
            cache.pop(key, None)
            return None
        cache.move_to_end(key)
        return value

    @staticmethod
    def _cache(
        cache: OrderedDict[str, tuple[float, Any]],
        key: str,
        value: Any,
        maximum: int,
    ) -> None:
        cache[key] = (time.monotonic() + CACHE_SECONDS, value)
        cache.move_to_end(key)
        while len(cache) > maximum:
            cache.popitem(last=False)


def validate_public_source_url(value: object) -> str:
    if not isinstance(value, str):
        raise RockKbError("invalid_knowledge_source")
    candidate = value.strip()
    if (
        not candidate
        or len(candidate) > 2_048
        or "\\" in candidate
        or any(ord(char) < 32 for char in candidate)
    ):
        raise RockKbError("invalid_knowledge_source")
    try:
        parsed = urllib.parse.urlsplit(candidate)
        port = parsed.port
        host = (parsed.hostname or "").rstrip(".").encode("idna").decode("ascii")
    except (UnicodeError, ValueError) as error:
        raise RockKbError("invalid_knowledge_source") from error
    if (
        parsed.scheme.lower() != "https"
        or not host
        or "." not in host
        or port not in (None, 443)
        or parsed.username
        or parsed.password
        or host == "localhost"
        or host.endswith((".localhost", ".local"))
    ):
        raise RockKbError("invalid_knowledge_source")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise RockKbError("invalid_knowledge_source")
    return urllib.parse.urlunsplit(
        ("https", host, parsed.path or "/", parsed.query, parsed.fragment)
    )


def open_public_source_url(value: str) -> bool:
    url = validate_public_source_url(value)
    executable = shutil.which("xdg-open")
    if not executable:
        return False
    try:
        subprocess.Popen(
            [executable, url],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False
    return True


def _validate_result_id(value: object) -> str:
    if not isinstance(value, str):
        raise RockKbError("invalid_knowledge_response")
    result_id = value.strip()
    if (
        not result_id
        or len(result_id) > MAX_RESULT_ID_LENGTH
        or any(ord(char) < 32 for char in result_id)
    ):
        raise RockKbError("invalid_knowledge_response")
    return result_id


def _safe_source_url(value: object) -> str:
    try:
        return validate_public_source_url(value)
    except RockKbError:
        return ""


def _first_source_url(row: dict[str, Any]) -> str:
    direct = _safe_source_url(row.get("url"))
    if direct:
        return direct
    payload = row.get("payload")
    candidates = payload.get("source_urls") if isinstance(payload, dict) else None
    if isinstance(candidates, list):
        for candidate in candidates[:50]:
            safe = _safe_source_url(candidate)
            if safe:
                return safe
    return ""


def _source_host(value: str) -> str:
    return (urllib.parse.urlsplit(value).hostname or "") if value else ""


def _kind(value: object) -> str:
    kind = sanitize_text(value, 60).casefold().replace("-", "_")
    return kind if kind.replace("_", "").isalnum() else ""


def _humanize(value: str) -> str:
    return " ".join(value.replace("_", "-").split("-")).capitalize()


def _snippet(value: object) -> str:
    text = sanitize_text(value, 500).strip(" .")
    return text if len(text) <= 157 else text[:156].rstrip() + "…"


def _version_label(row: dict[str, Any]) -> str:
    versions = row.get("rock_versions")
    if isinstance(versions, list):
        values = [sanitize_text(value, 30) for value in versions[:5]]
        values = [value for value in values if value]
        if values:
            return "Rock " + ", ".join(values)
    status = sanitize_text(row.get("version_scope_status"), 60)
    if status and status not in {"unprocessed", "unknown", "not_applicable"}:
        return _humanize(status)
    return "Version not specified"


def _sanitize_body(value: object, limit: int) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = "".join(
        char for char in text if char in {"\n", "\t"} or ord(char) >= 32
    )
    lines = [" ".join(line.split()) for line in cleaned.split("\n")]
    compact: list[str] = []
    for line in lines:
        if line or (compact and compact[-1]):
            compact.append(line)
    return "\n".join(compact).strip()[:limit]

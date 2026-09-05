from __future__ import annotations

import hashlib
import hmac
import http.client
import ipaddress
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .contracts import ALLOWED_RESULT_KEYS, allowlist, sanitize_text
from .http_security import HttpSecurityError, decode_bounded_json, redirect_free_opener
from .version import HTTP_USER_AGENT

ROCK_KB_ORIGIN = "https://rock-agent-kb.oneandall.church"
ROCK_KB_ATTRIBUTION = "Rock Agent Knowledge Base · ONE&ALL Church"
SEARCH_RESPONSE_LIMIT = 512 * 1024
DETAIL_RESPONSE_LIMIT = 2 * 1024 * 1024
COLLECTION_RESPONSE_LIMIT = 3 * 1024 * 1024
HTTP_TIMEOUT_SECONDS = 8
SEARCH_RESULT_LIMIT = 10
CACHE_SECONDS = 5 * 60
MAX_REGISTERED_RESULTS = 256
MAX_CACHED_SEARCHES = 40
MAX_RESULT_ID_LENGTH = 500
MAX_BODY_LENGTH = 20_000
MAX_RELATED_LINKS = 20
MODEL_MAP_SOURCE = "https://community.rockrms.com/modelmap"
XDG_OPEN = Path("/usr/bin/xdg-open")

KNOWLEDGE_SCOPE_ALIASES = {
    "mm": "model",
    "model": "model",
    "models": "model",
    "is": "issue",
    "issue": "issue",
    "issues": "issue",
    "idea": "idea",
    "ideas": "idea",
    "lava": "lava",
    "lc": "lava",
    "recipe": "recipe",
    "recipes": "recipe",
    "guide": "concept",
    "guides": "concept",
    "concept": "concept",
    "concepts": "concept",
}

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
    def search(
        self,
        query: str,
        limit: int = SEARCH_RESULT_LIMIT,
        *,
        kind: str = "",
        min_claim_tier: str = "source_backed",
    ) -> Any: ...

    def result(self, result_id: str) -> Any: ...

    def models(self) -> Any: ...

    def model(self, model_slug: str) -> Any: ...

    def lava_contexts(self) -> Any: ...

    def lava_context(self, context_id: str) -> Any: ...

    def concepts(self) -> Any: ...

    def concept(self, concept_id: str) -> str: ...

    def issue_search(self, query: str, limit: int = SEARCH_RESULT_LIMIT) -> Any: ...

    def idea_search(self, query: str, limit: int = SEARCH_RESULT_LIMIT) -> Any: ...


class RockKbHttpClient:
    """Fixed-origin, redirect-free, credentialless client for the public KB."""

    def __init__(self, opener: Any | None = None) -> None:
        self._opener = opener

    def search(
        self,
        query: str,
        limit: int = SEARCH_RESULT_LIMIT,
        *,
        kind: str = "",
        min_claim_tier: str = "source_backed",
    ) -> Any:
        normalized = sanitize_text(query, 120)
        if len(normalized) < 3 or not 1 <= limit <= SEARCH_RESULT_LIMIT:
            raise RockKbError("invalid_knowledge_query")
        safe_kind = _kind(kind)
        if kind and not safe_kind:
            raise RockKbError("invalid_knowledge_query")
        if min_claim_tier not in {"source_backed", "routing_context_only"}:
            raise RockKbError("invalid_knowledge_query")
        params = {
            "q": normalized,
            "limit": str(limit),
            "min_claim_tier": min_claim_tier,
            "detail": "compact",
        }
        if safe_kind:
            params["kind"] = safe_kind
        return self._get_json(
            "/search",
            params,
            SEARCH_RESPONSE_LIMIT,
        )

    def result(self, result_id: str) -> Any:
        safe_id = _validate_result_id(result_id)
        return self._get_json(
            "/results/" + urllib.parse.quote(safe_id, safe=""),
            {},
            DETAIL_RESPONSE_LIMIT,
        )

    def models(self) -> Any:
        return self._get_json(
            "/model-map/models", {}, COLLECTION_RESPONSE_LIMIT
        )

    def model(self, model_slug: str) -> Any:
        safe_id = _validate_target_id(model_slug)
        return self._get_json(
            "/model-map/models/" + urllib.parse.quote(safe_id, safe=""),
            {"format": "json"},
            DETAIL_RESPONSE_LIMIT,
        )

    def lava_contexts(self) -> Any:
        return self._get_json(
            "/lava-contexts", {}, COLLECTION_RESPONSE_LIMIT
        )

    def lava_context(self, context_id: str) -> Any:
        safe_id = _validate_target_id(context_id)
        return self._get_json(
            "/lava-contexts/" + urllib.parse.quote(safe_id, safe=""),
            {},
            DETAIL_RESPONSE_LIMIT,
        )

    def concepts(self) -> Any:
        return self._get_json("/concepts", {}, COLLECTION_RESPONSE_LIMIT)

    def concept(self, concept_id: str) -> str:
        safe_id = _validate_target_id(concept_id)
        return self._get_text(
            "/concepts/" + urllib.parse.quote(safe_id, safe="") + ".md",
            DETAIL_RESPONSE_LIMIT,
        )

    def issue_search(self, query: str, limit: int = SEARCH_RESULT_LIMIT) -> Any:
        return self._special_search("/rock-issues/search", query, limit)

    def idea_search(self, query: str, limit: int = SEARCH_RESULT_LIMIT) -> Any:
        return self._special_search("/rock-ideas/search", query, limit)

    def _special_search(self, path: str, query: str, limit: int) -> Any:
        normalized = sanitize_text(query, 120)
        if len(normalized) < 3 or not 1 <= limit <= SEARCH_RESULT_LIMIT:
            raise RockKbError("invalid_knowledge_query")
        return self._get_json(
            path, {"q": normalized, "limit": str(limit)}, SEARCH_RESPONSE_LIMIT
        )

    def _get_json(
        self, path: str, params: dict[str, str], maximum: int
    ) -> Any:
        raw = self._get_bytes(path, params, maximum, "application/json")
        try:
            return decode_bounded_json(raw)
        except HttpSecurityError as error:
            raise RockKbError("invalid_knowledge_response") from error

    def _get_text(self, path: str, maximum: int) -> str:
        raw = self._get_bytes(path, {}, maximum, "text/markdown")
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise RockKbError("invalid_knowledge_response") from error

    def _get_bytes(
        self, path: str, params: dict[str, str], maximum: int, accept: str
    ) -> bytes:
        if not _knowledge_path_allowed(path):
            raise RockKbError("knowledge_endpoint_not_allowed")
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(
            ROCK_KB_ORIGIN + path + ("?" + query if query else ""),
            headers={
                "Accept": accept,
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
        except (OSError, urllib.error.URLError, http.client.HTTPException) as error:
            raise RockKbError("knowledge_unavailable") from error
        if len(raw) > maximum:
            raise RockKbError("knowledge_response_out_of_bounds")
        return raw


@dataclass(frozen=True)
class _KnowledgeEntry:
    target_kind: str
    target_id: str
    source_url: str
    title: str


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
        self._collection_cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def search(self, query: str) -> list[dict[str, Any]]:
        normalized = sanitize_text(query, 120)
        scope, term = parse_knowledge_query(normalized)
        if len(term) < (2 if scope in {"model", "lava", "concept"} else 3):
            return []
        cache_key = scope + "\0" + term.casefold()
        cached = self._cached(self._search_cache, cache_key)
        if isinstance(cached, list):
            return [dict(item) for item in cached]

        if scope == "model":
            results = self._search_models(term)
        elif scope == "lava":
            results = self._search_lava(term)
        elif scope == "concept":
            results = self._search_concepts(term)
        else:
            if scope == "issue":
                payload = self._http.issue_search(term, SEARCH_RESULT_LIMIT)
                schemas = {"rock-kb-rock-issue-search-v1"}
            elif scope == "idea":
                payload = self._http.idea_search(term, SEARCH_RESULT_LIMIT)
                schemas = {"rock-kb-rock-idea-search-v1"}
            elif scope == "recipe":
                payload = self._http.search(
                    term,
                    SEARCH_RESULT_LIMIT,
                    kind="recipe",
                    min_claim_tier="routing_context_only",
                )
                schemas = {"rock-kb-search-result-v3"}
            else:
                payload = self._http.search(term, SEARCH_RESULT_LIMIT)
                schemas = {"rock-kb-search-result-v3"}
            results = self._results_from_payload(payload, schemas)
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

        if entry.target_kind == "model":
            detail = self._model_detail(public_id, entry)
        elif entry.target_kind == "lava":
            detail = self._lava_detail(public_id, entry)
        elif entry.target_kind == "concept":
            detail = self._concept_detail(public_id, entry)
        else:
            detail = self._result_detail(public_id, entry)
        self._cache(self._detail_cache, public_id, detail, MAX_REGISTERED_RESULTS)
        return dict(detail)

    def source_url(self, safe_id: str) -> str | None:
        entry = self._registry.get(sanitize_text(safe_id, 100))
        return entry.source_url if entry and entry.source_url else None

    def describe(self, safe_id: str) -> dict[str, Any]:
        public_id = sanitize_text(safe_id, 100)
        entry = self._registry.get(public_id)
        if not entry:
            raise RockKbError("knowledge_result_not_found")
        self._registry.move_to_end(public_id)
        actions = ["read"]
        if entry.source_url:
            actions.append("openSource")
        return {
            "safeId": public_id,
            "title": entry.title or "Rock Knowledge result",
            "kind": KIND_LABELS.get(entry.target_kind, "Knowledge"),
            "actions": actions,
            "expires": "broker_restart",
        }

    def _results_from_payload(
        self, payload: Any, schemas: set[str]
    ) -> list[dict[str, Any]]:
        if (
            not isinstance(payload, dict)
            or payload.get("schema") not in schemas
            or not isinstance(payload.get("results"), list)
            or len(payload["results"]) > 50
        ):
            raise RockKbError("invalid_knowledge_response")
        results: list[dict[str, Any]] = []
        for row in payload["results"][:SEARCH_RESULT_LIMIT]:
            public = self._search_result(row)
            if public:
                results.append(public)
        return results

    def _result_detail(
        self, public_id: str, entry: _KnowledgeEntry
    ) -> dict[str, Any]:
        payload = self._http.result(entry.target_id)
        if (
            not isinstance(payload, dict)
            or payload.get("schema") != "rock-kb-result-v1"
            or payload.get("status") != "ok"
            or payload.get("requested_result_id") != entry.target_id
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
        body = _without_duplicate_title(body, title)
        kind = _kind(row.get("kind"))
        authority = sanitize_text(row.get("authority_tier"), 60)
        claim_tier = sanitize_text(row.get("claim_tier"), 60)
        source_url = _first_source_url(row)
        self._registry[public_id] = _KnowledgeEntry(
            entry.target_kind, entry.target_id, source_url, title
        )
        self._registry.move_to_end(public_id)

        return {
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
            "links": self._related_result_links(row),
        }

    def _model_detail(
        self, public_id: str, entry: _KnowledgeEntry
    ) -> dict[str, Any]:
        payload = self._http.model(entry.target_id)
        if not isinstance(payload, dict) or not isinstance(payload.get("model"), dict):
            raise RockKbError("invalid_knowledge_response")
        model = payload["model"]
        identity = model.get("identity")
        counts = model.get("counts")
        relationships = model.get("relationships")
        if not isinstance(identity, dict) or not isinstance(counts, dict):
            raise RockKbError("invalid_knowledge_response")
        slug = _validate_target_id(identity.get("model_slug"))
        if slug.casefold() != entry.target_id.casefold():
            raise RockKbError("invalid_knowledge_response")
        title = sanitize_text(identity.get("model_name"), 160)
        if not title:
            raise RockKbError("invalid_knowledge_response")
        required = model.get("required_fields")
        required_names: list[str] = []
        if isinstance(required, list):
            required_names = [
                sanitize_text(item.get("name"), 80)
                for item in required[:12]
                if isinstance(item, dict) and sanitize_text(item.get("name"), 80)
            ]
        lines = [
            "Category: " + (sanitize_text(identity.get("model_category"), 80) or "Uncategorized"),
            "Rock version: " + (sanitize_text(identity.get("rock_version"), 30) or "Not specified"),
            "Properties: " + str(_safe_count(counts.get("properties"))),
            "Database properties: " + str(_safe_count(counts.get("database_properties"))),
            "Lava properties: " + str(_safe_count(counts.get("lava_properties"))),
            "Relationships: " + str(_safe_count(counts.get("relationships"))),
            "Methods: " + str(_safe_count(counts.get("methods"))),
        ]
        if required_names:
            lines.extend(["", "Required fields", " · ".join(required_names)])
        links: list[dict[str, Any]] = []
        seen: set[str] = set()
        if isinstance(relationships, list):
            for relationship in relationships[:100]:
                if not isinstance(relationship, dict):
                    continue
                target = sanitize_text(relationship.get("target_model_slug"), 100)
                title_value = sanitize_text(relationship.get("related_model"), 120)
                via = sanitize_text(relationship.get("property_name"), 100)
                if not target or target.casefold() in seen:
                    continue
                try:
                    target = _validate_target_id(target)
                except RockKbError:
                    continue
                seen.add(target.casefold())
                links.append(self._link("model", target, title_value or _humanize_slug(target), "Model Map", "via " + via if via else "Related model"))
                if len(links) >= MAX_RELATED_LINKS:
                    break
        self._registry[public_id] = _KnowledgeEntry(
            "model", slug, MODEL_MAP_SOURCE, title
        )
        return {
            "safeId": public_id,
            "title": title,
            "kind": "Model Map",
            "body": "\n".join(lines),
            "trust": "Source confirmed",
            "claimTier": "Structured reference",
            "version": "Rock " + (sanitize_text(identity.get("rock_version"), 30) or "version not specified"),
            "sourceHost": _source_host(MODEL_MAP_SOURCE),
            "canOpenSource": True,
            "attribution": ROCK_KB_ATTRIBUTION,
            "links": links,
        }

    def _lava_detail(
        self, public_id: str, entry: _KnowledgeEntry
    ) -> dict[str, Any]:
        payload = self._http.lava_context(entry.target_id)
        if (
            not isinstance(payload, dict)
            or payload.get("schema") != "rock-kb-lava-context-surface-result-v2"
            or payload.get("status") != "ok"
            or not isinstance(payload.get("surface"), dict)
            or not isinstance(payload.get("roots"), list)
        ):
            raise RockKbError("invalid_knowledge_response")
        surface = payload["surface"]
        context_id = _validate_target_id(surface.get("context_id"))
        if context_id.casefold() != entry.target_id.casefold():
            raise RockKbError("invalid_knowledge_response")
        title = sanitize_text(surface.get("surface_name"), 160)
        roots = payload["roots"][:50]
        root_names = [
            sanitize_text(row.get("root_key"), 80)
            for row in roots
            if isinstance(row, dict) and sanitize_text(row.get("root_key"), 80)
        ]
        lines = [
            "Context: " + context_id,
            "Family: " + _humanize(sanitize_text(surface.get("context_family"), 80)),
            "Surface type: " + _humanize(sanitize_text(surface.get("surface_type"), 80)),
            "Rock version: " + (sanitize_text(surface.get("source_version"), 30) or "Not specified"),
            "Available roots: " + (", ".join(root_names) if root_names else "None documented"),
        ]
        links: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in roots:
            if not isinstance(row, dict):
                continue
            model_slug = sanitize_text(row.get("model_slug"), 100)
            if model_slug and model_slug.casefold() not in seen:
                try:
                    model_slug = _validate_target_id(model_slug)
                except RockKbError:
                    model_slug = ""
                if model_slug:
                    seen.add(model_slug.casefold())
                    links.append(self._link("model", model_slug, sanitize_text(row.get("root_key"), 120) or _humanize_slug(model_slug), "Model Map", "Lava root"))
        for concept_id in _string_values(surface.get("concept_ids"), 30):
            if len(links) >= MAX_RELATED_LINKS:
                break
            if "concept\0" + concept_id.casefold() in seen:
                continue
            seen.add("concept\0" + concept_id.casefold())
            links.append(self._link("concept", concept_id, _humanize_slug(concept_id), "Guide", "Related guide"))
        source_url = _first_root_source(roots)
        self._registry[public_id] = _KnowledgeEntry(
            "lava", context_id, source_url, title or _humanize_slug(context_id)
        )
        return {
            "safeId": public_id,
            "title": title or _humanize_slug(context_id),
            "kind": "Lava context",
            "body": "\n".join(lines),
            "trust": "Source confirmed",
            "claimTier": "Structured reference",
            "version": "Rock " + (sanitize_text(surface.get("source_version"), 30) or "version not specified"),
            "sourceHost": _source_host(source_url),
            "canOpenSource": bool(source_url),
            "attribution": ROCK_KB_ATTRIBUTION,
            "links": links[:MAX_RELATED_LINKS],
        }

    def _concept_detail(
        self, public_id: str, entry: _KnowledgeEntry
    ) -> dict[str, Any]:
        body = _sanitize_body(self._http.concept(entry.target_id), MAX_BODY_LENGTH)
        if not body:
            raise RockKbError("invalid_knowledge_response")
        title = _markdown_title(body) or _humanize_slug(entry.target_id)
        body = _without_duplicate_title(body, title)
        source_url = ROCK_KB_ORIGIN + "/concepts/" + urllib.parse.quote(entry.target_id, safe="") + ".md"
        self._registry[public_id] = _KnowledgeEntry(
            "concept", entry.target_id, source_url, title
        )
        return {
            "safeId": public_id,
            "title": title,
            "kind": "Guide",
            "body": body,
            "trust": "Public knowledge",
            "claimTier": "Concept guide",
            "version": "Version varies by source",
            "sourceHost": _source_host(source_url),
            "canOpenSource": True,
            "attribution": ROCK_KB_ATTRIBUTION,
            "links": [],
        }

    def _search_models(self, term: str) -> list[dict[str, Any]]:
        payload = self._collection("models", self._http.models)
        if (
            not isinstance(payload, dict)
            or payload.get("schema") != "rock-kb-model-map-model-list-v1"
            or not isinstance(payload.get("models"), list)
            or len(payload["models"]) > 1_000
        ):
            raise RockKbError("invalid_knowledge_response")
        rows = _ranked_rows(payload["models"], term, ("model_name", "model_title", "model_slug", "model_category"))
        results: list[dict[str, Any]] = []
        for row in rows[:SEARCH_RESULT_LIMIT]:
            try:
                slug = _validate_target_id(row.get("model_slug"))
            except RockKbError:
                continue
            title = sanitize_text(row.get("model_name"), 160)
            if not title:
                continue
            subtitle = (sanitize_text(row.get("model_category"), 80) or "Model") + " · " + str(_safe_count(row.get("property_count"))) + " properties · " + str(_safe_count(row.get("method_count"))) + " methods"
            results.append(self._public_result("model", slug, title, subtitle, "Rock " + (sanitize_text(row.get("rock_version"), 30) or "version not specified"), MODEL_MAP_SOURCE))
        return results

    def _search_lava(self, term: str) -> list[dict[str, Any]]:
        payload = self._collection("lava", self._http.lava_contexts)
        if (
            not isinstance(payload, dict)
            or payload.get("schema") != "rock-kb-lava-context-surface-list-v1"
            or not isinstance(payload.get("surfaces"), list)
            or len(payload["surfaces"]) > 500
        ):
            raise RockKbError("invalid_knowledge_response")
        rows = _ranked_rows(payload["surfaces"], term, ("surface_name", "context_id", "context_family", "surface_type", "root_keys"))
        results: list[dict[str, Any]] = []
        for row in rows[:SEARCH_RESULT_LIMIT]:
            try:
                context_id = _validate_target_id(row.get("context_id"))
            except RockKbError:
                continue
            results.append(
                self._public_result(
                    "lava",
                    context_id,
                    sanitize_text(row.get("surface_name"), 160)
                    or _humanize_slug(context_id),
                    _humanize(sanitize_text(row.get("context_family"), 80))
                    + " · "
                    + str(_safe_count(row.get("direct_root_count")))
                    + " roots",
                    "Rock "
                    + (
                        sanitize_text(row.get("source_version"), 30)
                        or "version not specified"
                    ),
                    "",
                )
            )
        return results

    def _search_concepts(self, term: str) -> list[dict[str, Any]]:
        payload = self._collection("concepts", self._http.concepts)
        rows = payload.get("rows") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or len(rows) > 500:
            raise RockKbError("invalid_knowledge_response")
        matches = _ranked_rows(rows, term, ("title", "concept_id", "depends_on_topics"))
        results: list[dict[str, Any]] = []
        for row in matches[:SEARCH_RESULT_LIMIT]:
            try:
                concept_id = _validate_target_id(row.get("concept_id"))
            except RockKbError:
                continue
            results.append(self._public_result("concept", concept_id, sanitize_text(row.get("title"), 160) or _humanize_slug(concept_id), str(_safe_count(row.get("source_count"))) + " sources", "Concept guide", ""))
        return results

    def _collection(self, key: str, loader: Any) -> Any:
        cached = self._cached(self._collection_cache, key)
        if cached is not None:
            return cached
        payload = loader()
        self._cache(self._collection_cache, key, payload, 5)
        return payload

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
        target_kind = "result"
        target_id = result_id
        if kind == "model_map" and result_id.startswith("model_map:"):
            target_kind = "model"
            target_id = result_id.rsplit(":", 1)[-1]
            source_url = MODEL_MAP_SOURCE
        elif kind == "concept" and result_id.startswith("concept:"):
            target_kind = "concept"
            target_id = result_id.rsplit(":", 1)[-1]
        return self._public_result(
            target_kind,
            target_id,
            title,
            snippet or KIND_LABELS.get(kind, "Public Rock knowledge"),
            TRUST_LABELS.get(authority, _humanize(authority) or "Public knowledge"),
            source_url,
        )

    def _public_result(
        self,
        target_kind: str,
        target_id: str,
        title: str,
        subtitle: str,
        status: str,
        source_url: str,
    ) -> dict[str, Any]:
        safe_id = self._register(target_kind, target_id, source_url, title)
        return allowlist(
            {
                "category": "Knowledge",
                "safeId": safe_id,
                "title": title,
                "subtitle": subtitle,
                "status": status,
                "canOpen": True,
            },
            ALLOWED_RESULT_KEYS,
        )

    def _register(
        self, target_kind: str, target_id: str, source_url: str, title: str = ""
    ) -> str:
        digest = hmac.new(
            self._key,
            ("rock-kb\0" + target_kind + "\0" + target_id).encode(),
            hashlib.sha256,
        ).hexdigest()[:32]
        safe_id = "kb-" + digest
        self._registry[safe_id] = _KnowledgeEntry(
            target_kind,
            target_id,
            source_url,
            sanitize_text(title, 160),
        )
        self._registry.move_to_end(safe_id)
        while len(self._registry) > MAX_REGISTERED_RESULTS:
            evicted, _ = self._registry.popitem(last=False)
            self._detail_cache.pop(evicted, None)
        return safe_id

    def _link(
        self, target_kind: str, target_id: str, title: str, kind: str, subtitle: str
    ) -> dict[str, str]:
        return {
            "safeId": self._register(target_kind, target_id, "", title),
            "title": sanitize_text(title, 160),
            "kind": sanitize_text(kind, 60),
            "subtitle": sanitize_text(subtitle, 160),
        }

    def _related_result_links(self, row: dict[str, Any]) -> list[dict[str, str]]:
        links: list[dict[str, str]] = []
        seen: set[str] = set()

        def append(target_kind: str, target_id: str, title: str, kind: str, subtitle: str) -> None:
            if len(links) >= MAX_RELATED_LINKS:
                return
            try:
                safe_target = _validate_result_id(target_id) if target_kind == "result" else _validate_target_id(target_id)
            except RockKbError:
                return
            key = target_kind + "\0" + safe_target.casefold()
            if key in seen:
                return
            seen.add(key)
            links.append(self._link(target_kind, safe_target, title, kind, subtitle))

        concepts = _string_values(row.get("concepts"), 30)
        concept = sanitize_text(row.get("concept"), 100)
        if concept:
            concepts.insert(0, concept)
        payload = row.get("payload")
        if isinstance(payload, dict):
            single = sanitize_text(payload.get("concept_id"), 100)
            if single:
                concepts.append(single)
            concepts.extend(_string_values(payload.get("concept_ids"), 30))
            for entity in _string_values(payload.get("entities"), 50):
                slug = _slugify(entity)
                if slug:
                    append("model", slug, entity, "Model Map", "Referenced model")
            model_links = payload.get("model_map_links")
            if isinstance(model_links, list):
                for value in model_links[:50]:
                    if isinstance(value, dict):
                        slug = sanitize_text(value.get("model_slug"), 100)
                        title = sanitize_text(value.get("model_name") or value.get("model_title"), 160)
                    else:
                        reference = sanitize_text(value, 160)
                        slug = reference.rsplit(":", 1)[-1] if reference.startswith("model_map:") else _slugify(reference)
                        title = _humanize_slug(slug)
                    if slug:
                        append("model", slug, title or _humanize_slug(slug), "Model Map", "Referenced model")
            for related in _string_values(payload.get("related_result_ids"), 50):
                append("result", related, _result_id_title(related), "Related", "Related knowledge")
            for key_name, prefix, label in (
                ("related_issue_ids", "rock_issue:", "Rock issue"),
                ("related_idea_ids", "rock_idea:", "Rock idea"),
            ):
                for related in _string_values(payload.get(key_name), 50):
                    target = related if ":" in related else prefix + related
                    append("result", target, _result_id_title(target), label, "Related community report")
        for concept_id in concepts:
            append("concept", concept_id, _humanize_slug(concept_id), "Guide", "Related guide")
        return links

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


def parse_knowledge_query(value: object) -> tuple[str, str]:
    """Return the local Knowledge area and its query without changing server syntax."""

    text = sanitize_text(value, 120)
    prefix, separator, remainder = text.partition(":")
    scope = KNOWLEDGE_SCOPE_ALIASES.get(prefix.casefold()) if separator else None
    return (scope or "all", remainder.strip() if scope else text)


def _knowledge_path_allowed(path: str) -> bool:
    if path in {
        "/search",
        "/model-map/models",
        "/lava-contexts",
        "/concepts",
        "/rock-issues/search",
        "/rock-ideas/search",
    }:
        return True
    prefixes = (
        "/results/",
        "/model-map/models/",
        "/lava-contexts/",
        "/concepts/",
    )
    return any(path.startswith(prefix) and len(path) > len(prefix) for prefix in prefixes)


def _validate_target_id(value: object) -> str:
    target = sanitize_text(value, 120)
    if (
        not target
        or target in {".", ".."}
        or "/" in target
        or "\\" in target
        or not all(char.isalnum() or char in {"-", "_", "."} for char in target)
    ):
        raise RockKbError("invalid_knowledge_response")
    return target


def _ranked_rows(
    rows: list[Any], term: str, fields: tuple[str, ...]
) -> list[dict[str, Any]]:
    needle = term.casefold()
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        values: list[tuple[int, str]] = []
        for field_index, field in enumerate(fields):
            raw = row.get(field)
            if isinstance(raw, list):
                values.extend(
                    (field_index, sanitize_text(value, 160)) for value in raw[:30]
                )
            else:
                values.append((field_index, sanitize_text(raw, 160)))
        haystacks = [
            (field_index, value.casefold())
            for field_index, value in values
            if value
        ]
        matching = [
            (field_index, value)
            for field_index, value in haystacks
            if needle in value
        ]
        if not matching:
            continue
        score = min(
            field_index * 3
            + (0 if value == needle else 1 if value.startswith(needle) else 2)
            for field_index, value in matching
        )
        ranked.append((score, haystacks[0][1] if haystacks else "", row))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ranked]


def _string_values(value: object, maximum: int) -> list[str]:
    if not isinstance(value, list):
        return []
    values: list[str] = []
    for item in value[:maximum]:
        text = sanitize_text(item, 120)
        if text:
            values.append(text)
    return values


def _safe_count(value: object) -> int:
    return value if isinstance(value, int) and 0 <= value <= 1_000_000 else 0


def _humanize_slug(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("_", "-").split("-") if part)


def _slugify(value: str) -> str:
    slug = "-".join("".join(char.lower() if char.isalnum() else " " for char in value).split())
    try:
        return _validate_target_id(slug)
    except RockKbError:
        return ""


def _result_id_title(value: str) -> str:
    tail = value.rsplit(":", 1)[-1]
    return _humanize_slug(tail) or "Related knowledge"


def _markdown_title(body: str) -> str:
    for line in body.splitlines()[:20]:
        if line.startswith("# "):
            return sanitize_text(line[2:], 160)
    return ""


def _first_root_source(roots: list[Any]) -> str:
    for row in roots[:50]:
        if isinstance(row, dict):
            source = _safe_source_url(row.get("source_url"))
            if source:
                return source
    return ""


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
    if not XDG_OPEN.is_file():
        return False
    try:
        subprocess.Popen(
            [str(XDG_OPEN), url],
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
    try:
        result_id.encode("utf-8")
    except UnicodeEncodeError as error:
        raise RockKbError("invalid_knowledge_response") from error
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


def _without_duplicate_title(body: str, title: str) -> str:
    candidate = body.lstrip("# ")
    if not candidate.casefold().startswith(title.casefold()):
        return body
    remainder = candidate[len(title) :]
    if remainder and remainder[0] not in {" ", "\t", "\n", ".", ":", "-", "—"}:
        return body
    trimmed = remainder.lstrip(" \t\n.:-—")
    return trimmed or body


def _sanitize_body(value: object, limit: int) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = "".join(
        char
        for char in text
        if (char in {"\n", "\t"} or ord(char) >= 32)
        and not 0xD800 <= ord(char) <= 0xDFFF
    )
    lines = [" ".join(line.split()) for line in cleaned.split("\n")]
    compact: list[str] = []
    for line in lines:
        if line or (compact and compact[-1]):
            compact.append(line)
    return "\n".join(compact).strip()[:limit]

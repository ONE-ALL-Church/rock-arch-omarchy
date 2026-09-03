from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Context(StrEnum):
    DEV = "DEV"
    PROD = "PROD"


DEVELOPER_MODE_ENV = "ROCK_ARCH_DEVELOPER_MODE"


def developer_mode_enabled() -> bool:
    """Return whether the explicit process-level developer gate is enabled."""

    return os.environ.get(DEVELOPER_MODE_ENV) == "1"


class HealthState(StrEnum):
    UNKNOWN = "unknown"
    STALE = "stale"
    FAILED = "failed"
    HEALTHY = "healthy"


CATEGORIES = (
    "People",
    "Groups",
    "Group Types",
    "Workflows",
    "Jobs",
    "Pages",
    "Content Channel Types",
    "Content Channel Items",
)

KNOWLEDGE_CATEGORY = "Knowledge"
KNOWLEDGE_SCOPE_ALIASES = frozenset({"kb", "knowledge"})

SEARCH_SCOPE_ALIASES = {
    "p": "People",
    "person": "People",
    "people": "People",
    "g": "Groups",
    "group": "Groups",
    "groups": "Groups",
    "gt": "Group Types",
    "grouptype": "Group Types",
    "grouptypes": "Group Types",
    "w": "Workflows",
    "wt": "Workflows",
    "workflow": "Workflows",
    "workflows": "Workflows",
    "workflowtype": "Workflows",
    "workflowtypes": "Workflows",
    "j": "Jobs",
    "job": "Jobs",
    "jobs": "Jobs",
    "pg": "Pages",
    "page": "Pages",
    "pages": "Pages",
    "ct": "Content Channel Types",
    "contenttype": "Content Channel Types",
    "contenttypes": "Content Channel Types",
    "channeltype": "Content Channel Types",
    "channeltypes": "Content Channel Types",
    "c": "Content Channel Items",
    "content": "Content Channel Items",
    "contents": "Content Channel Items",
    "item": "Content Channel Items",
    "items": "Content Channel Items",
}

ALLOWED_RESULT_KEYS = frozenset(
    {"category", "safeId", "title", "subtitle", "status", "canOpen"}
)
ALLOWED_PERSON_KEYS = frozenset({"safeId", "displayName", "subtitle", "campus"})
ALLOWED_LINK_KEYS = frozenset({"safeId", "title", "section", "isShared"})
ALLOWED_QUICK_RETURN_KEYS = frozenset(
    {"safeId", "title", "kind", "lastUsedAt"}
)


@dataclass(frozen=True)
class Capability:
    name: str
    state: HealthState
    detail: str

    def public_dict(self) -> dict[str, str]:
        return {"name": self.name, "state": self.state.value, "detail": self.detail}


def sanitize_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").replace("\x00", "").split())
    return text[:limit]


def parse_search_query(value: Any) -> tuple[str, str | None]:
    """Split a recognized entity or public-knowledge prefix from a query."""

    text = sanitize_text(value, 120)
    prefix, separator, remainder = text.partition(":")
    if separator and prefix.lower() in KNOWLEDGE_SCOPE_ALIASES:
        return remainder.strip(), KNOWLEDGE_CATEGORY
    category = SEARCH_SCOPE_ALIASES.get(prefix.lower()) if separator else None
    return (remainder.strip(), category) if category else (text, None)


def allowlist(record: dict[str, Any], keys: frozenset[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in keys:
        if key not in record:
            continue
        result[key] = (
            bool(record[key])
            if key in {"canOpen", "isShared"}
            else sanitize_text(record.get(key), 160)
        )
    return result

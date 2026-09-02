from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Context(StrEnum):
    DEV = "DEV"
    PROD = "PROD"


DEVELOPER_MODE_ENV = "ROCK_LENS_DEVELOPER_MODE"


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
    "Workflows",
    "Jobs",
    "Pages",
    "Content Channel Items",
)

SEARCH_SCOPE_ALIASES = {
    "p": "People",
    "person": "People",
    "people": "People",
    "g": "Groups",
    "group": "Groups",
    "groups": "Groups",
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
ALLOWED_QUICK_RETURN_KEYS = frozenset({"safeId", "title", "kind"})


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
    """Split a recognized entity prefix from a bounded search query."""

    text = sanitize_text(value, 120)
    prefix, separator, remainder = text.partition(":")
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

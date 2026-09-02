from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Context(StrEnum):
    DEV = "DEV"
    PROD = "PROD"


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

ALLOWED_RESULT_KEYS = frozenset({"category", "safeId", "title", "subtitle", "status"})
ALLOWED_PERSON_KEYS = frozenset({"safeId", "displayName", "subtitle", "campus"})


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


def allowlist(record: dict[str, Any], keys: frozenset[str]) -> dict[str, str]:
    return {key: sanitize_text(record.get(key), 160) for key in keys if key in record}

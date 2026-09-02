from __future__ import annotations

from .contracts import (
    ALLOWED_PERSON_KEYS,
    ALLOWED_RESULT_KEYS,
    CATEGORIES,
    allowlist,
)

_RECORDS = (
    {
        "category": "People",
        "safeId": "mock-person-ada",
        "title": "Ada Rivera",
        "subtitle": "Volunteer Coordinator",
        "status": "Active",
    },
    {
        "category": "Groups",
        "safeId": "mock-group-hillside",
        "title": "Hillside Community",
        "subtitle": "Small Group",
        "status": "Active",
    },
    {
        "category": "Workflows",
        "safeId": "mock-workflow-welcome",
        "title": "New Guest Follow-up",
        "subtitle": "Workflow Type",
        "status": "Active",
    },
    {
        "category": "Jobs",
        "safeId": "mock-job-sync",
        "title": "Sample Data Sync",
        "subtitle": "Last run 12 minutes ago",
        "status": "Succeeded",
    },
    {
        "category": "Pages",
        "safeId": "mock-page-dashboard",
        "title": "Operations Dashboard",
        "subtitle": "Internal Page",
        "status": "Published",
    },
    {
        "category": "Content Channel Items",
        "safeId": "mock-content-weekend",
        "title": "Weekend Update",
        "subtitle": "News Item",
        "status": "Approved",
    },
)

_PERSONS = {
    "mock-person-ada": {
        "safeId": "mock-person-ada",
        "displayName": "Ada Rivera",
        "subtitle": "Volunteer Coordinator · synthetic record",
        "campus": "North Campus",
    }
}


class MockAdapter:
    def search(self, query: str, limit: int = 18) -> list[dict[str, str]]:
        needle = " ".join(query.lower().split())[:120]
        rows = [
            r for r in _RECORDS if not needle or needle in " ".join(r.values()).lower()
        ]
        return [
            allowlist(dict(r), ALLOWED_RESULT_KEYS)
            for r in rows[: max(1, min(limit, 24))]
        ]

    def person_quick_look(self, safe_id: str) -> dict[str, str] | None:
        row = _PERSONS.get(safe_id)
        return allowlist(dict(row), ALLOWED_PERSON_KEYS) if row else None

    def categories(self) -> tuple[str, ...]:
        return CATEGORIES

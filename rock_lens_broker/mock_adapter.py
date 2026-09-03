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
        "subtitle": "Age 34 · Spouse Mateo Rivera · North Campus",
        "status": "Member",
        "canOpen": False,
    },
    {
        "category": "Groups",
        "safeId": "mock-group-hillside",
        "title": "Hillside Community",
        "subtitle": "Small Group",
        "status": "Active",
        "canOpen": False,
    },
    {
        "category": "Group Types",
        "safeId": "mock-group-type-small-group",
        "title": "Small Group",
        "subtitle": "Group type",
        "status": "Live",
        "canOpen": False,
    },
    {
        "category": "Workflows",
        "safeId": "mock-workflow-welcome",
        "title": "New Guest Follow-up",
        "subtitle": "Workflow Type",
        "status": "Active",
        "canOpen": False,
    },
    {
        "category": "Jobs",
        "safeId": "mock-job-sync",
        "title": "Sample Data Sync",
        "subtitle": "Last run 12 minutes ago",
        "status": "Succeeded",
        "canOpen": False,
    },
    {
        "category": "Pages",
        "safeId": "mock-page-dashboard",
        "title": "Operations Dashboard",
        "subtitle": "Internal Page",
        "status": "Published",
        "canOpen": False,
    },
    {
        "category": "Content Channel Types",
        "safeId": "mock-content-type-blog",
        "title": "Blog",
        "subtitle": "Content channel type",
        "status": "Live",
        "canOpen": False,
    },
    {
        "category": "Content Channel Items",
        "safeId": "mock-content-weekend",
        "title": "Weekend Update",
        "subtitle": "News Item",
        "status": "Approved",
        "canOpen": False,
    },
)

_PERSONS = {
    "mock-person-ada": {
        "safeId": "mock-person-ada",
        "displayName": "Ada Rivera",
        "subtitle": "Age 34 · Spouse Mateo Rivera · Member",
        "campus": "Campus · North Campus",
    }
}


class MockAdapter:
    def search(
        self, query: str, limit: int = 18, category: str | None = None
    ) -> list[dict[str, object]]:
        needle = " ".join(query.lower().split())[:120]
        rows = [
            r
            for r in _RECORDS
            if (category is None or r["category"] == category)
            and (
                not needle
                or needle in " ".join(str(value) for value in r.values()).lower()
            )
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

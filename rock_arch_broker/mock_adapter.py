from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from .contracts import (
    ALLOWED_LINK_KEYS,
    ALLOWED_PERSON_KEYS,
    ALLOWED_QUICK_RETURN_KEYS,
    ALLOWED_RESULT_KEYS,
    CATEGORIES,
    allowlist,
    sanitize_text,
)

_RECORDS = (
    {
        "category": "People",
        "safeId": "mock-person-ada",
        "title": "Ada Rivera",
        "subtitle": "Age 34 · Spouse Mateo Rivera · North Campus",
        "status": "Member",
        "canOpen": True,
        "searchTerms": "17 6f9619ff-8b86-d011-b42d-00c04fc964ff",
    },
    {
        "category": "People",
        "safeId": "mock-person-jordan",
        "title": "Jordan Lee",
        "subtitle": "Age 42 · Spouse Taylor Lee · North Campus",
        "status": "Staff",
        "canOpen": True,
        "searchTerms": "42 7c9e6679-7425-40de-944b-e07fc1f90ae7",
    },
    {
        "category": "People",
        "safeId": "mock-person-maya",
        "title": "Maya Thompson",
        "subtitle": "Age 29 · Family Alex and Noah · North Campus",
        "status": "Member",
        "canOpen": True,
        "searchTerms": "108 550e8400-e29b-41d4-a716-446655440000",
    },
    {
        "category": "Groups",
        "safeId": "mock-group-welcome",
        "title": "North Campus Welcome Team",
        "subtitle": "Serve Team · North Campus",
        "status": "Active",
        "canOpen": True,
        "searchTerms": "42",
    },
    {
        "category": "Groups",
        "safeId": "mock-group-hillside",
        "title": "Hillside Community",
        "subtitle": "Small Group · Tuesday evenings",
        "status": "Active",
        "canOpen": True,
        "searchTerms": "108",
    },
    {
        "category": "Group Types",
        "safeId": "mock-group-type-serve-team",
        "title": "Serve Team",
        "subtitle": "Group type · 24 active groups",
        "status": "Active",
        "canOpen": True,
        "searchTerms": "42",
    },
    {
        "category": "Group Types",
        "safeId": "mock-group-type-small-group",
        "title": "Small Group",
        "subtitle": "Group type · 86 active groups",
        "status": "Active",
        "canOpen": True,
        "searchTerms": "108",
    },
    {
        "category": "Workflows",
        "safeId": "mock-workflow-welcome",
        "title": "New Guest Follow-up",
        "subtitle": "Workflow type · North Campus",
        "status": "Active",
        "canOpen": True,
        "searchTerms": "42",
    },
    {
        "category": "Workflows",
        "safeId": "mock-workflow-care",
        "title": "Care Request",
        "subtitle": "Workflow type · Pastoral Care",
        "status": "Active",
        "canOpen": True,
        "searchTerms": "108",
    },
    {
        "category": "Jobs",
        "safeId": "mock-job-sync",
        "title": "North Campus Data Sync",
        "subtitle": "Last run 12 minutes ago",
        "status": "Succeeded",
        "canOpen": True,
        "searchTerms": "42",
    },
    {
        "category": "Jobs",
        "safeId": "mock-job-reminders",
        "title": "Send Group Reminders",
        "subtitle": "Next run today at 4:00 PM",
        "status": "Idle",
        "canOpen": True,
        "searchTerms": "108",
    },
    {
        "category": "Pages",
        "safeId": "mock-page-dashboard",
        "title": "North Campus Dashboard",
        "subtitle": "Internal page · Operations",
        "status": "Published",
        "canOpen": True,
        "searchTerms": "42",
    },
    {
        "category": "Pages",
        "safeId": "mock-page-checkin",
        "title": "Check-in Central",
        "subtitle": "Internal page · Weekend tools",
        "status": "Published",
        "canOpen": True,
        "searchTerms": "108",
    },
    {
        "category": "Content Channel Types",
        "safeId": "mock-content-type-campus",
        "title": "Campus Updates",
        "subtitle": "Content channel type · 4 channels",
        "status": "Active",
        "canOpen": True,
        "searchTerms": "42 north",
    },
    {
        "category": "Content Channel Types",
        "safeId": "mock-content-type-sermons",
        "title": "Sermon Library",
        "subtitle": "Content channel type · Media",
        "status": "Active",
        "canOpen": True,
        "searchTerms": "108",
    },
    {
        "category": "Content Channel Items",
        "safeId": "mock-content-weekend",
        "title": "North Campus Weekend Update",
        "subtitle": "Campus Updates · Sep 6",
        "status": "Approved",
        "canOpen": True,
        "searchTerms": "42",
    },
    {
        "category": "Content Channel Items",
        "safeId": "mock-content-sermon",
        "title": "A Place to Belong",
        "subtitle": "Sermon Library · Week 3",
        "status": "Approved",
        "canOpen": True,
        "searchTerms": "108",
    },
)

_PERSONS = {
    "mock-person-ada": {
        "safeId": "mock-person-ada",
        "displayName": "Ada Rivera",
        "subtitle": "Age 34 · Spouse Mateo Rivera · Member",
        "campus": "Campus · North Campus",
    },
    "mock-person-jordan": {
        "safeId": "mock-person-jordan",
        "displayName": "Jordan Lee",
        "subtitle": "Age 42 · Spouse Taylor Lee · Staff",
        "campus": "Campus · North Campus",
    },
    "mock-person-maya": {
        "safeId": "mock-person-maya",
        "displayName": "Maya Thompson",
        "subtitle": "Age 29 · Family Alex and Noah · Member",
        "campus": "Campus · North Campus",
    },
}

_PERSONAL_LINKS = (
    {
        "safeId": "mock-link-weekend",
        "title": "Weekend Dashboard",
        "section": "Weekend Operations",
        "isShared": True,
    },
    {
        "safeId": "mock-link-checkin",
        "title": "Check-in Central",
        "section": "Weekend Operations",
        "isShared": True,
    },
    {
        "safeId": "mock-link-care",
        "title": "Care Requests",
        "section": "Pastoral Care",
        "isShared": False,
    },
    {
        "safeId": "mock-link-volunteers",
        "title": "Volunteer Scheduling",
        "section": "Ministry Tools",
        "isShared": False,
    },
    {
        "safeId": "mock-link-giving",
        "title": "Giving Analytics",
        "section": "Reporting",
        "isShared": False,
    },
)

_KNOWLEDGE_RESULTS = (
    {
        "category": "Knowledge",
        "safeId": "kb-mock-group-member",
        "title": "Group Member",
        "subtitle": "Entity properties, relationships, and required fields",
        "status": "Model Map",
        "canOpen": True,
        "scope": "model",
        "searchTerms": "group member membership person group role model map entity properties",
    },
    {
        "category": "Knowledge",
        "safeId": "kb-mock-checkin-labels",
        "title": "Check-in labels stop printing after a device change",
        "subtitle": "Troubleshooting steps and confirmed causes",
        "status": "Rock issue",
        "canOpen": True,
        "scope": "issue",
        "searchTerms": "check in check-in labels printer device issue",
    },
    {
        "category": "Knowledge",
        "safeId": "kb-mock-person-context",
        "title": "Current Person Lava context",
        "subtitle": "Available roots and common person properties",
        "status": "Lava context",
        "canOpen": True,
        "scope": "lava",
        "searchTerms": "lava current person context roots properties",
    },
    {
        "category": "Knowledge",
        "safeId": "kb-mock-attendance-recipe",
        "title": "Launch an attendance workflow from a group page",
        "subtitle": "A reusable workflow and Lava recipe",
        "status": "Recipe",
        "canOpen": True,
        "scope": "recipe",
        "searchTerms": "attendance workflow group page launch recipe lava",
    },
    {
        "category": "Knowledge",
        "safeId": "kb-mock-workflow-guide",
        "title": "How workflow types, activities, and actions fit together",
        "subtitle": "Concept guide for Rock automation",
        "status": "Guide",
        "canOpen": True,
        "scope": "concept",
        "searchTerms": "workflow types activities actions automation guide concept",
    },
    {
        "category": "Knowledge",
        "safeId": "kb-mock-global-search-idea",
        "title": "Expand global search with entity-aware shortcuts",
        "subtitle": "Community feature request and discussion",
        "status": "Rock idea",
        "canOpen": True,
        "scope": "idea",
        "searchTerms": "global search entity shortcuts idea feature",
    },
)

_KNOWLEDGE_DETAILS: dict[str, dict[str, Any]] = {
    "kb-mock-group-member": {
        "title": "Group Member",
        "kind": "Model Map",
        "body": "Category: Groups\nRock version: 17.2\nProperties: 31\nDatabase properties: 18\nLava properties: 26\nRelationships: 7\nMethods: 4\n\nRequired fields\nGroup · Person · GroupRole · GroupMemberStatus",
        "trust": "Source confirmed",
        "claimTier": "Structured reference",
        "version": "Rock 17.2",
        "sourceHost": "community.rockrms.com",
        "canOpenSource": True,
        "attribution": "Rock Agent Knowledge Base · ONE&ALL Church",
        "links": [
            {
                "safeId": "kb-mock-workflow-guide",
                "title": "Workflow automation concepts",
                "kind": "Guide",
                "subtitle": "Use group data in workflow actions",
            },
            {
                "safeId": "kb-mock-person-context",
                "title": "Current Person",
                "kind": "Lava context",
                "subtitle": "Person properties available in Lava",
            },
        ],
    },
    "kb-mock-checkin-labels": {
        "title": "Check-in labels stop printing after a device change",
        "kind": "Rock issue",
        "body": "Confirm that the kiosk still has the intended printer selected, then verify the label route and printer proxy. A device rename can leave the kiosk pointing at a printer that no longer exists. Re-select the printer before changing templates or label data.",
        "trust": "Community reviewed",
        "claimTier": "Source backed",
        "version": "Rock 17.x",
        "sourceHost": "community.rockrms.com",
        "canOpenSource": True,
        "attribution": "Rock Agent Knowledge Base · ONE&ALL Church",
        "links": [],
    },
    "kb-mock-person-context": {
        "title": "Current Person Lava context",
        "kind": "Lava context",
        "body": "Surface: CurrentPerson\nRoots: CurrentPerson · CurrentPersonAlias\n\nCommon properties\nFullName · NickName · PrimaryCampus · ConnectionStatusValue · RecordStatusValue",
        "trust": "Source confirmed",
        "claimTier": "Structured reference",
        "version": "Rock 17.2",
        "sourceHost": "community.rockrms.com",
        "canOpenSource": True,
        "attribution": "Rock Agent Knowledge Base · ONE&ALL Church",
        "links": [
            {
                "safeId": "kb-mock-group-member",
                "title": "Group Member",
                "kind": "Model Map",
                "subtitle": "Membership relationships and properties",
            }
        ],
    },
    "kb-mock-attendance-recipe": {
        "title": "Launch an attendance workflow from a group page",
        "kind": "Recipe",
        "body": "Create a workflow action button on the group page, pass the selected group as an entity attribute, and keep the workflow type limited to the campuses and roles that should run it. Validate the group and occurrence before recording attendance.",
        "trust": "Community reviewed",
        "claimTier": "Source backed",
        "version": "Rock 17.x",
        "sourceHost": "rock-agent-kb.oneandall.church",
        "canOpenSource": True,
        "attribution": "Rock Agent Knowledge Base · ONE&ALL Church",
        "links": [
            {
                "safeId": "kb-mock-workflow-guide",
                "title": "Workflow automation concepts",
                "kind": "Guide",
                "subtitle": "Activities, actions, and attributes",
            }
        ],
    },
    "kb-mock-workflow-guide": {
        "title": "How workflow types, activities, and actions fit together",
        "kind": "Guide",
        "body": "A workflow type defines the reusable process. Activities group ordered actions, while attributes carry the data each action needs. Use activation rules to start only the applicable activity and completion rules to end the workflow intentionally.",
        "trust": "Official",
        "claimTier": "Source backed",
        "version": "Rock 17.x",
        "sourceHost": "community.rockrms.com",
        "canOpenSource": True,
        "attribution": "Rock Agent Knowledge Base · ONE&ALL Church",
        "links": [
            {
                "safeId": "kb-mock-attendance-recipe",
                "title": "Launch an attendance workflow",
                "kind": "Recipe",
                "subtitle": "A practical group-page example",
            }
        ],
    },
    "kb-mock-global-search-idea": {
        "title": "Expand global search with entity-aware shortcuts",
        "kind": "Rock idea",
        "body": "The proposal adds explicit entity prefixes to global search so a user can move directly from intent to a narrower result set. It also recommends retaining an unscoped search for discovery.",
        "trust": "Community report · unreviewed",
        "claimTier": "Routing context only",
        "version": "Version not specified",
        "sourceHost": "community.rockrms.com",
        "canOpenSource": True,
        "attribution": "Rock Agent Knowledge Base · ONE&ALL Church",
        "links": [],
    },
}

_MAGNUS_FILES = {
    "mock-magnus-file-navigation": (
        "Navigation Action.xaml",
        '<Rock:NavigateToPageAction PageGuid="{{ Page.Guid }}" />\n',
    ),
    "mock-magnus-file-routing": (
        "Home Routing Logic.lava",
        "{% if CurrentPerson %}/page/23{% else %}/page/24{% endif %}\n",
    ),
    "mock-magnus-file-page-layout": (
        "Layout.xaml",
        '<VerticalStackLayout Spacing="16">\n  <Rock:Zone Name="Main" />\n</VerticalStackLayout>\n',
    ),
    "mock-magnus-file-page-styles": (
        "Page Styles.xaml",
        '<Style TargetType="Label" Class="welcome-title">\n  <Setter Property="FontSize" Value="28" />\n</Style>\n',
    ),
    "mock-magnus-file-page-events": (
        "Page Events.lava",
        "{% assign campus = CurrentPerson.PrimaryCampus %}\n{% comment %}Prepare page state.{% endcomment %}\n",
    ),
    "mock-magnus-file-pre-content": (
        "pre-content",
        '<Grid RowDefinitions="Auto,*">\n',
    ),
    "mock-magnus-file-content": (
        "content.lava",
        '{% assign campus = CurrentPerson.PrimaryCampus %}\n<Label Text="Welcome to {{ campus.Name }}" />\n',
    ),
    "mock-magnus-file-post-content": (
        "post-content",
        "</Grid>\n",
    ),
    "mock-magnus-file-theme": (
        "theme.less",
        "@brand-accent: #7aa2f7;\n@content-spacing: 1rem;\n",
    ),
    "mock-magnus-file-shortcode-template": (
        "template.lava",
        '<article class="event-card">{{ EventItem.Name }}</article>\n',
    ),
    "mock-magnus-file-shortcode-docs": (
        "documentation.md",
        "# Event Card\n\nRenders an event item as a compact card.\n",
    ),
    "mock-magnus-file-rigging": (
        "application-rigging.lava",
        "{% assign routePrefix = 'api/volunteers' %}\n",
    ),
    "mock-magnus-file-endpoint": (
        "code-template.lava",
        "{% webrequest url:'https://example.invalid' %}{% endwebrequest %}\n",
    ),
    "mock-magnus-file-robots": (
        "robots.txt",
        "User-agent: *\nDisallow: /admin/\n",
    ),
    "mock-magnus-file-tv-styles": (
        "Application Styles.xaml",
        "<ResourceDictionary>\n  <!-- Weekend TV styles -->\n</ResourceDictionary>\n",
    ),
}

_MAGNUS_FOLDERS: dict[str, dict[str, Any]] = {
    "": {
        "title": "Magnus",
        "items": [
            {
                "safeId": "mock-magnus-root-websites",
                "title": "Websites",
                "kind": "folder",
                "actions": [],
            },
            {
                "safeId": "mock-magnus-root-mobileapps",
                "title": "Mobile Applications",
                "kind": "folder",
                "actions": [],
            },
            {
                "safeId": "mock-magnus-root-shortcodes",
                "title": "Lava Shortcodes",
                "kind": "folder",
                "actions": [],
            },
            {
                "safeId": "mock-magnus-root-lavaapps",
                "title": "Lava Applications",
                "kind": "folder",
                "actions": [],
            },
            {
                "safeId": "mock-magnus-root-files",
                "title": "Server File System",
                "kind": "folder",
                "actions": [],
            },
            {
                "safeId": "mock-magnus-root-appletv",
                "title": "Apple TV Applications",
                "kind": "folder",
                "actions": [],
            },
        ],
    },
    "mock-magnus-root-websites": {
        "title": "Websites",
        "items": [
            {
                "safeId": "mock-magnus-site-rock-solid",
                "title": "Rock Solid Church",
                "kind": "folder",
                "actions": [],
            },
            {
                "safeId": "mock-magnus-site-staff",
                "title": "Staff Portal",
                "kind": "folder",
                "actions": [],
            },
        ],
    },
    "mock-magnus-site-rock-solid": {
        "title": "Rock Solid Church",
        "items": [
            {
                "safeId": "mock-magnus-site-pages",
                "title": "Pages",
                "kind": "folder",
                "actions": [],
            },
            {
                "safeId": "mock-magnus-site-theme",
                "title": "Theme",
                "kind": "folder",
                "actions": [],
            },
        ],
    },
    "mock-magnus-site-staff": {"title": "Staff Portal", "items": []},
    "mock-magnus-site-pages": {"title": "Pages", "items": []},
    "mock-magnus-site-theme": {
        "title": "Theme",
        "items": [
            {
                "safeId": "mock-magnus-file-theme",
                "title": "theme.less",
                "kind": "file",
                "actions": ["download", "copyHash", "copy"],
            }
        ],
    },
    "mock-magnus-root-mobileapps": {
        "title": "Mobile Applications",
        "items": [
            {
                "safeId": "mock-magnus-app-weekend",
                "title": "Weekend Mobile",
                "kind": "folder",
                "actions": ["build"],
            }
        ],
    },
    "mock-magnus-app-weekend": {
        "title": "Weekend Mobile",
        "items": [
            {
                "safeId": "mock-magnus-app-pages",
                "title": "Pages",
                "kind": "folder",
                "actions": [],
            },
            {
                "safeId": "mock-magnus-app-shell",
                "title": "Shell Navigation",
                "kind": "folder",
                "actions": [],
            },
            {
                "safeId": "mock-magnus-app-routing",
                "title": "Home Routing Logic",
                "kind": "folder",
                "actions": [],
            },
        ],
    },
    "mock-magnus-app-shell": {
        "title": "Shell Navigation",
        "items": [
            {
                "safeId": "mock-magnus-file-navigation",
                "title": "Navigation Action.xaml",
                "kind": "file",
                "actions": ["download", "copyHash", "copy"],
            }
        ],
    },
    "mock-magnus-app-routing": {
        "title": "Home Routing Logic",
        "items": [
            {
                "safeId": "mock-magnus-file-routing",
                "title": "Home Routing Logic.lava",
                "kind": "file",
                "actions": ["download", "copyHash", "copy"],
            }
        ],
    },
    "mock-magnus-app-pages": {
        "title": "Pages",
        "items": [
            {
                "safeId": "mock-magnus-page-home",
                "title": "Home",
                "kind": "folder",
                "actions": [],
            },
            {
                "safeId": "mock-magnus-page-groups",
                "title": "Groups",
                "kind": "folder",
                "actions": [],
            },
        ],
    },
    "mock-magnus-page-groups": {"title": "Groups", "items": []},
    "mock-magnus-page-home": {
        "title": "Home",
        "items": [
            {
                "safeId": "mock-magnus-file-page-layout",
                "title": "Layout.xaml",
                "kind": "file",
                "actions": ["download", "copyHash", "copy", "view"],
            },
            {
                "safeId": "mock-magnus-file-page-styles",
                "title": "Page Styles.xaml",
                "kind": "file",
                "actions": ["download", "copyHash", "copy", "view"],
            },
            {
                "safeId": "mock-magnus-file-page-events",
                "title": "Page Events.lava",
                "kind": "file",
                "actions": ["download", "copyHash", "copy", "view"],
            },
            {
                "safeId": "mock-magnus-page-blocks",
                "title": "Blocks",
                "kind": "folder",
                "actions": [],
            },
        ],
    },
    "mock-magnus-page-blocks": {
        "title": "Blocks",
        "items": [
            {
                "safeId": "mock-magnus-block-welcome",
                "title": "Welcome Content",
                "kind": "folder",
                "actions": [],
            }
        ],
    },
    "mock-magnus-block-welcome": {
        "title": "Welcome Content",
        "items": [
            {
                "safeId": "mock-magnus-file-pre-content",
                "title": "pre-content",
                "kind": "file",
                "actions": ["download", "copyHash", "copy"],
            },
            {
                "safeId": "mock-magnus-file-content",
                "title": "content.lava",
                "kind": "file",
                "actions": ["download", "copyHash", "copy", "view"],
            },
            {
                "safeId": "mock-magnus-file-post-content",
                "title": "post-content",
                "kind": "file",
                "actions": ["download", "copyHash", "copy"],
            },
        ],
    },
    "mock-magnus-root-shortcodes": {
        "title": "Lava Shortcodes",
        "items": [
            {
                "safeId": "mock-magnus-shortcode-event",
                "title": "Event Card",
                "kind": "folder",
                "actions": [],
            }
        ],
    },
    "mock-magnus-shortcode-event": {
        "title": "Event Card",
        "items": [
            {
                "safeId": "mock-magnus-file-shortcode-template",
                "title": "template.lava",
                "kind": "file",
                "actions": ["download", "copyHash", "copy"],
            },
            {
                "safeId": "mock-magnus-file-shortcode-docs",
                "title": "documentation.md",
                "kind": "file",
                "actions": ["download", "copyHash", "copy"],
            },
        ],
    },
    "mock-magnus-root-lavaapps": {
        "title": "Lava Applications",
        "items": [
            {
                "safeId": "mock-magnus-lavaapp-volunteers",
                "title": "Volunteer Check-in",
                "kind": "folder",
                "actions": [],
            }
        ],
    },
    "mock-magnus-lavaapp-volunteers": {
        "title": "Volunteer Check-in",
        "items": [
            {
                "safeId": "mock-magnus-file-rigging",
                "title": "application-rigging.lava",
                "kind": "file",
                "actions": ["download", "copyHash", "copy"],
            },
            {
                "safeId": "mock-magnus-lavaapp-endpoints",
                "title": "Endpoints",
                "kind": "folder",
                "actions": [],
            },
        ],
    },
    "mock-magnus-lavaapp-endpoints": {
        "title": "Endpoints",
        "items": [
            {
                "safeId": "mock-magnus-file-endpoint",
                "title": "code-template.lava",
                "kind": "file",
                "actions": ["download", "copyHash", "copy"],
            }
        ],
    },
    "mock-magnus-root-files": {
        "title": "Server File System",
        "items": [
            {
                "safeId": "mock-magnus-file-robots",
                "title": "robots.txt",
                "kind": "file",
                "actions": ["download", "copyHash", "copy"],
            }
        ],
    },
    "mock-magnus-root-appletv": {
        "title": "Apple TV Applications",
        "items": [
            {
                "safeId": "mock-magnus-appletv-weekend",
                "title": "Weekend TV",
                "kind": "folder",
                "actions": [],
            }
        ],
    },
    "mock-magnus-appletv-weekend": {
        "title": "Weekend TV",
        "items": [
            {
                "safeId": "mock-magnus-file-tv-styles",
                "title": "Application Styles.xaml",
                "kind": "file",
                "actions": ["download", "copyHash", "copy"],
            }
        ],
    },
}


class MockAdapter:
    def search(
        self, query: str, limit: int = 18, category: str | None = None
    ) -> list[dict[str, object]]:
        needle = " ".join(query.lower().split())[:120]
        rows = [
            row
            for row in _RECORDS
            if (category is None or row["category"] == category)
            and (
                not needle
                or all(
                    term in " ".join(str(value) for value in row.values()).lower()
                    for term in needle.split()
                )
            )
        ]
        return [
            allowlist(dict(row), ALLOWED_RESULT_KEYS)
            for row in rows[: max(1, min(limit, 24))]
        ]

    def person_quick_look(self, safe_id: str) -> dict[str, str] | None:
        row = _PERSONS.get(safe_id)
        return allowlist(dict(row), ALLOWED_PERSON_KEYS) if row else None

    def personal_links(self) -> list[dict[str, object]]:
        return [allowlist(dict(row), ALLOWED_LINK_KEYS) for row in _PERSONAL_LINKS]

    def has_navigation_item(self, safe_id: str) -> bool:
        candidate = sanitize_text(safe_id, 100)
        return any(
            row["safeId"] == candidate
            for row in (*_PERSONAL_LINKS, *self.quick_returns(), *_RECORDS)
        )

    @staticmethod
    def is_recent_build(safe_id: str) -> bool:
        return sanitize_text(safe_id, 100) == "mock-recent-build"

    @staticmethod
    def is_magnus_build(safe_id: str) -> bool:
        return sanitize_text(safe_id, 100) == "mock-magnus-app-weekend"

    def quick_returns(self) -> list[dict[str, object]]:
        now = datetime.now(UTC)
        rows: tuple[dict[str, Any], ...] = (
            {
                "safeId": "mock-recent-weekend",
                "title": "Weekend Dashboard",
                "kind": "Page",
                "lastUsedAt": now - timedelta(minutes=2),
            },
            {
                "safeId": "mock-recent-ada",
                "title": "Ada Rivera",
                "kind": "Person",
                "lastUsedAt": now - timedelta(minutes=4),
            },
            {
                "safeId": "mock-recent-build",
                "title": "Deploy Weekend Mobile",
                "kind": "Magnus Build",
                "lastUsedAt": now - timedelta(minutes=5),
            },
            {
                "safeId": "mock-recent-hillside",
                "title": "Hillside Community",
                "kind": "Group",
                "lastUsedAt": now - timedelta(hours=1, minutes=18),
            },
        )
        return [
            allowlist(
                {
                    **row,
                    "lastUsedAt": row["lastUsedAt"].isoformat().replace("+00:00", "Z"),
                },
                ALLOWED_QUICK_RETURN_KEYS,
            )
            for row in rows
        ]

    def knowledge_search(self, query: str) -> list[dict[str, object]]:
        normalized = sanitize_text(query, 120).casefold()
        prefix, separator, remainder = normalized.partition(":")
        scopes = {
            "mm": "model",
            "model": "model",
            "is": "issue",
            "issue": "issue",
            "idea": "idea",
            "lava": "lava",
            "recipe": "recipe",
            "guide": "concept",
            "concept": "concept",
        }
        scope = scopes.get(prefix) if separator else None
        term = remainder.strip() if scope else normalized
        rows = [
            row
            for row in _KNOWLEDGE_RESULTS
            if (scope is None or row["scope"] == scope)
            and (
                not term
                or all(
                    word
                    in f"{row['title']} {row['subtitle']} {row['status']} {row['searchTerms']}".casefold()
                    for word in term.split()
                )
            )
        ]
        return [allowlist(dict(row), ALLOWED_RESULT_KEYS) for row in rows]

    def knowledge_detail(self, safe_id: str) -> dict[str, Any] | None:
        detail = _KNOWLEDGE_DETAILS.get(sanitize_text(safe_id, 100))
        return {"safeId": safe_id, **detail} if detail else None

    def magnus_status(self) -> dict[str, Any]:
        return {
            "available": True,
            "configured": True,
            "state": "available",
            "mode": "controlled",
            "capabilities": [
                "browse",
                "preview",
                "hash",
                "download",
                "copy",
                "open",
                "mobile_app_build",
            ],
            "server": "preview.rockarch.local",
        }

    def magnus_browse(self, safe_id: str = "") -> dict[str, Any] | None:
        folder = _MAGNUS_FOLDERS.get(sanitize_text(safe_id, 100))
        return (
            {
                "folderId": safe_id,
                "title": folder["title"],
                "items": [dict(row) for row in folder["items"]],
            }
            if folder
            else None
        )

    def magnus_preview(self, safe_id: str) -> dict[str, Any] | None:
        item = _MAGNUS_FILES.get(sanitize_text(safe_id, 100))
        if not item:
            return None
        title, content = item
        raw = content.encode()
        actions = ["download", "copyHash", "copy"]
        if safe_id in {
            "mock-magnus-file-page-layout",
            "mock-magnus-file-page-styles",
            "mock-magnus-file-page-events",
            "mock-magnus-file-content",
        }:
            actions.append("view")
        return {
            "safeId": safe_id,
            "title": title,
            "content": content,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "sizeBytes": len(raw),
            "previewAvailable": True,
            "actions": actions,
        }

    def magnus_builds(self) -> list[dict[str, Any]]:
        accepted = (
            (datetime.now(UTC) - timedelta(minutes=5))
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
        return [
            {
                "buildId": "build-00000000000000000000000000000001",
                "title": "Weekend Mobile",
                "state": "accepted",
                "acceptedAt": accepted,
                "message": "Magnus accepted the deployment request.",
                "statusSource": "local",
                "completionVerifiable": False,
                "persisted": False,
            }
        ]

    def categories(self) -> tuple[str, ...]:
        return CATEGORIES

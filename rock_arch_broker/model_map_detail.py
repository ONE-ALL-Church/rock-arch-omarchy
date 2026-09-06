"""Bounded, plain-text Model Map sections for the Knowledge reader and CLI."""

from __future__ import annotations

from typing import Any

from .contracts import sanitize_text

MAX_MODEL_ROWS = 250
MAX_MODEL_TEXT = 80_000
PROPERTY_GROUPS = (
    "database", "not_mapped", "lava", "lava_non_database", "required",
    "enum", "defined_value", "obsolete",
)
PROPERTY_FLAGS = (
    ("required", "Required"), ("database", "Database"), ("lava", "Lava"),
    ("enum", "Enum"), ("defined_value", "Defined value"),
    ("inherited", "Inherited"), ("virtual", "Virtual"),
    ("not_mapped", "Not mapped"), ("obsolete", "Obsolete"),
)


def _text(value: object, limit: int = 2_000) -> str:
    text = sanitize_text(value, limit + 1) if isinstance(value, str) else ""
    return text[:limit] + "…" if len(text) > limit else text


def _property(row: dict[str, Any]) -> dict[str, str]:
    flags = row.get("flags")
    flags = flags if isinstance(flags, dict) else {}
    lines = [_text(row.get("description"))]
    related = row.get("related_entities")
    if isinstance(related, list):
        names = [_text(item.get("text"), 120) for item in related[:20] if isinstance(item, dict)]
        if any(names):
            lines.append("Related: " + " · ".join(name for name in names if name))
    values = row.get("enum_values")
    if isinstance(values, list) and values:
        lines.append("Reference values (source snapshot):" if flags.get("defined_value") is True else "Values:")
        for item in values[:30]:
            if not isinstance(item, dict):
                continue
            value, label = _text(item.get("value"), 120), _text(item.get("label"), 200)
            if value or label:
                lines.append(" · ".join(part for part in (value, label) if part))
        if len(values) > 30:
            lines.append("Additional values omitted.")
    obsolete = _text(row.get("obsolete_message"), 500)
    if obsolete:
        lines.append("Obsolete: " + obsolete)
    return {
        "title": _text(row.get("name"), 160),
        "subtitle": " · ".join(label for key, label in PROPERTY_FLAGS if flags.get(key) is True),
        "body": "\n".join(line for line in lines if line),
    }


def _method(row: dict[str, Any]) -> dict[str, str]:
    description = _text(row.get("description"))
    obsolete = _text(row.get("obsolete_message"), 500)
    return {
        "title": _text(row.get("signature"), 500),
        "subtitle": " · ".join(label for key, label in (("inherited", "Inherited"), ("is_obsolete", "Obsolete")) if row.get(key) is True),
        "body": description + ("\nObsolete: " + obsolete if obsolete else ""),
    }


def model_sections(model: dict[str, Any]) -> list[dict[str, Any]]:
    """Deduplicate overlapping property groups without forwarding raw KB records."""
    groups = model.get("property_groups")
    groups = groups if isinstance(groups, dict) else {}
    properties: dict[str, dict[str, Any]] = {}
    for key in PROPERTY_GROUPS:
        rows = groups.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows[:MAX_MODEL_ROWS + 1]:
            if not isinstance(row, dict):
                continue
            name = _text(row.get("name"), 160)
            if name:
                properties.setdefault(name.casefold(), row)
    methods = model.get("methods")
    methods = [row for row in methods[:MAX_MODEL_ROWS + 1] if isinstance(row, dict)] if isinstance(methods, list) else []
    counts = model.get("counts")
    counts = counts if isinstance(counts, dict) else {}
    budget = MAX_MODEL_TEXT
    sections: list[dict[str, Any]] = []
    for key, title, rows, render in (
        ("properties", "Properties", list(properties.values()), _property),
        ("methods", "Methods", methods, _method),
    ):
        rendered = [render(row) for row in rows]
        rendered = sorted((row for row in rendered if row["title"]), key=lambda row: row["title"].casefold())
        count = counts.get(key)
        count = count if type(count) is int and 0 <= count <= 1_000_000 else 0
        total = max(count, len(rendered))
        shown: list[dict[str, str]] = []
        shortened = False
        for row in rendered[:MAX_MODEL_ROWS]:
            if len(row["body"]) > 3_000:
                row["body"] = row["body"][:3_000] + "…"
                shortened = True
            size = sum(len(value) for value in row.values())
            if size > budget:
                break
            budget -= size
            shown.append(row)
        notice = ""
        if len(shown) < total:
            notice = f"Showing {len(shown)} of {total} {title.lower()} from the public reference. Open source for more."
        elif shortened:
            notice = "Some descriptions are shortened. Open source for more."
        elif not shown:
            notice = "None documented in this source snapshot."
        sections.append({"key": key, "title": title, "total": total, "rows": shown, "notice": notice})
    return sections

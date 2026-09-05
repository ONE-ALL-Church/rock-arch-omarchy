from __future__ import annotations

from typing import Any

from .contracts import CATEGORIES
from .profiles import DEFAULT_PREFERENCES, DEFAULT_TAB_ORDER, EDITABLE_PREFERENCES

PROTOCOL_VERSION = 1


def settings_schema() -> dict[str, Any]:
    fields = {
        key: {"type": "boolean", "default": DEFAULT_PREFERENCES[key]}
        for key in EDITABLE_PREFERENCES
        if isinstance(DEFAULT_PREFERENCES[key], bool)
    }
    fields["enabledCategories"] = {
        "type": "array", "items": list(CATEGORIES), "uniqueItems": True,
        "default": list(CATEGORIES),
    }
    fields["tabOrder"] = {
        "type": "array", "items": list(DEFAULT_TAB_ORDER),
        "rule": "Include each tab ID exactly once, in the desired order.",
        "default": list(DEFAULT_TAB_ORDER),
    }
    return {
        "fields": fields,
        "read": "rock-arch settings get",
        "write": "rock-arch settings set KEY JSON_VALUE",
        "batchWrite": "rock-arch settings set --stdin",
        "batchInput": "JSON object containing editable setting names and values; applied atomically",
        "terminalAccess": "Rock commands can be disabled; owner-local settings remain available for recovery.",
        "shortcuts": "Use rock-arch shortcuts status|check|set|remove; set and remove require --confirm.",
    }


def protocol_schema() -> dict[str, Any]:
    """Return the stable, machine-readable CLI contract."""

    return {
        "name": "rock-arch",
        "protocolVersion": PROTOCOL_VERSION,
        "output": {
            "format": "one JSON object",
            "successStream": "stdout",
            "errorStream": "stderr",
        },
        "exitCodes": {
            "0": "success",
            "2": "invalid input, missing confirmation, or cancelled dry-run",
            "3": "broker, socket, or terminal-access failure",
            "4": "bounded operation failure",
            "130": "interactive input cancelled",
        },
        "queryInput": {
            "positional": "supported for compatibility",
            "private": "use --stdin, '-' as the query, or omit the query",
            "maximumBytes": 8192,
        },
        "credentialInput": {
            "commands": ["login --stdin", "profiles add --stdin"],
            "format": "JSON object through stdin; never put credentials in command arguments",
            "required": ["username", "password"],
            "newProfileRequired": ["name", "domain", "username", "password"],
            "maximumBytes": 8192,
        },
        "safeIds": {
            "prefixes": ["rock-", "quick-", "kb-", "magnus-"],
            "lifetime": "broker process unless explicitly documented otherwise",
            "describeCommand": "rock-arch describe SAFE_ID",
        },
        "confirmation": {
            "flag": "--confirm",
            "previewFlag": "--dry-run",
            "rule": "external, destructive, clipboard, download, update, and build actions require confirmation",
        },
        "commands": [
            "status",
            "doctor",
            "schema",
            "login",
            "capabilities",
            "search",
            "person",
            "describe",
            "knowledge",
            "links",
            "open",
            "profiles",
            "magnus",
            "updates",
            "settings",
            "shortcuts",
            "ui",
        ],
        "settings": settings_schema(),
        "buildStatus": {
            "source": "local receipt",
            "terminalState": "accepted",
            "completionVerifiable": False,
        },
    }

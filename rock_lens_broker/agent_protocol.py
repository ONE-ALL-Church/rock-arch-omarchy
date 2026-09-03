from __future__ import annotations

from typing import Any

PROTOCOL_VERSION = 1


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
            "ui",
        ],
        "buildStatus": {
            "source": "local receipt",
            "terminalState": "accepted",
            "completionVerifiable": False,
        },
    }

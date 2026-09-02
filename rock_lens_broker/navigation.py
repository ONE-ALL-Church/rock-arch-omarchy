from __future__ import annotations

import shutil
import subprocess
import urllib.parse
from dataclasses import dataclass

from .contracts import sanitize_text
from .origin import OriginError, validate_rock_origin

MAX_ROCK_URL_LENGTH = 2_048


class NavigationError(Exception):
    """A stable navigation error that does not disclose a target URL."""


@dataclass(frozen=True)
class NavigationTarget:
    title: str
    kind: str
    type_order: int
    url: str


def validate_rock_url(value: str, origin: str) -> str:
    if not isinstance(value, str):
        raise NavigationError("invalid_rock_url")
    candidate = value.strip()
    if (
        not candidate
        or len(candidate) > MAX_ROCK_URL_LENGTH
        or "\\" in candidate
        or any(ord(char) < 32 for char in candidate)
    ):
        raise NavigationError("invalid_rock_url")

    try:
        safe_origin = validate_rock_origin(origin)
    except OriginError as error:
        raise NavigationError("invalid_rock_origin") from error
    absolute = urllib.parse.urljoin(safe_origin + "/", candidate)
    parsed = urllib.parse.urlsplit(absolute)
    canonical = urllib.parse.urlsplit(safe_origin)
    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname != canonical.hostname
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
    ):
        raise NavigationError("rock_url_not_allowed")
    return urllib.parse.urlunsplit(
        (
            "https",
            canonical.hostname or "",
            parsed.path or "/",
            parsed.query,
            parsed.fragment,
        )
    )


def open_rock_url(value: str, origin: str) -> bool:
    url = validate_rock_url(value, origin)
    executable = shutil.which("xdg-open")
    if not executable:
        return False
    try:
        subprocess.Popen(
            [executable, url],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False
    return True


def clean_target(
    title: object, kind: object, type_order: int, url: str, origin: str
) -> NavigationTarget:
    safe_title = sanitize_text(title, 160)
    safe_kind = sanitize_text(kind, 80)
    if not safe_title or not safe_kind or not 0 <= type_order <= 1_000:
        raise NavigationError("invalid_navigation_target")
    return NavigationTarget(
        safe_title, safe_kind, type_order, validate_rock_url(url, origin)
    )

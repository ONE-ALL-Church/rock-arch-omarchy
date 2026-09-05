from __future__ import annotations

import json
import math
import urllib.request
from typing import Any


class HttpSecurityError(ValueError):
    """A private validation failure for shared HTTP trust boundaries."""


class RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def redirect_free_opener(injected: Any | None = None) -> Any:
    """Return a test opener or a production opener that refuses redirects."""

    return injected or urllib.request.build_opener(RejectRedirects())


def validate_rock_cookie_header(value: object, maximum: int = 16 * 1024) -> str:
    """Validate the complete Cookie header used for authenticated Rock calls."""

    if (
        not isinstance(value, str)
        or not value.startswith(".ROCK=")
        or len(value) < 7
        or len(value) > maximum
        or any(not 33 <= ord(char) <= 126 or char in ';,\\"' for char in value)
    ):
        raise HttpSecurityError("invalid_rock_cookie")
    return value


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise HttpSecurityError("invalid_json")
    return number


def _reject_constant(_value: str) -> None:
    raise HttpSecurityError("invalid_json")


def decode_bounded_json(raw: bytes | bytearray | str) -> Any:
    """Decode bounded response bytes without leaking parser-specific failures."""

    try:
        return json.loads(raw, parse_float=_finite_float, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as error:
        raise HttpSecurityError("invalid_json") from error

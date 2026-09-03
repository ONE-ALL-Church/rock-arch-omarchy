from __future__ import annotations

import ipaddress
import urllib.parse

# A reserved, non-routable example origin used only to initialize adapters before
# a profile is selected. Real requests require the user's validated profile origin.
DEFAULT_ROCK_ORIGIN = "https://rock.example.org"
MAX_ORIGIN_LENGTH = 300


class OriginError(ValueError):
    """Stable validation failure for a Rock instance origin."""


def validate_rock_origin(value: object) -> str:
    if not isinstance(value, str):
        raise OriginError("invalid_rock_origin")
    candidate = value.strip()
    if not candidate or len(candidate) > MAX_ORIGIN_LENGTH:
        raise OriginError("invalid_rock_origin")
    if "://" not in candidate:
        candidate = "https://" + candidate
    if "\\" in candidate or any(ord(char) < 33 for char in candidate):
        raise OriginError("invalid_rock_origin")

    try:
        parsed = urllib.parse.urlsplit(candidate)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise OriginError("invalid_rock_origin") from error
    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or port not in (None, 443)
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or hostname.endswith(".")
    ):
        raise OriginError("invalid_rock_origin")

    try:
        normalized_host = hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as error:
        raise OriginError("invalid_rock_origin") from error
    if not normalized_host or len(normalized_host) > 253:
        raise OriginError("invalid_rock_origin")
    try:
        ipaddress.ip_address(normalized_host)
    except ValueError:
        labels = normalized_host.split(".")
        if any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            or any(not (char.isalnum() or char == "-") for char in label)
            for label in labels
        ):
            raise OriginError("invalid_rock_origin")

    netloc = f"[{normalized_host}]" if ":" in normalized_host else normalized_host
    return f"https://{netloc}"

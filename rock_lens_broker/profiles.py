from __future__ import annotations

import json
import os
import re
import stat
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .contracts import CATEGORIES, sanitize_text
from .instance import InstanceStore
from .origin import OriginError, validate_rock_origin

MAX_PROFILE_STORE_BYTES = 64 * 1024
MAX_PROFILES = 20
PROFILE_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
DEFAULT_PREFERENCES: dict[str, Any] = {
    "showPersonContext": True,
    "recentLinks": True,
    "closeAfterOpen": True,
    "automaticUpdates": False,
    "enabledCategories": list(CATEGORIES),
}


class ProfileError(Exception):
    """A stable profile error that contains no secret material."""


@dataclass(frozen=True)
class RockProfile:
    profile_id: str
    name: str
    origin: str

    def public_dict(self, active_profile_id: str) -> dict[str, Any]:
        return {
            "id": self.profile_id,
            "name": self.name,
            "origin": self.origin,
            "isActive": self.profile_id == active_profile_id,
        }


def validate_profile_id(value: object) -> str:
    if not isinstance(value, str) or not PROFILE_ID_PATTERN.fullmatch(value):
        raise ProfileError("invalid_profile")
    return value


def default_profile_name(origin: str) -> str:
    return urlsplit(origin).hostname or "Rock"


class ProfileStore:
    """Owner-only non-secret Rock profile metadata and launcher preferences."""

    def __init__(self, path: Path, legacy_instance: InstanceStore) -> None:
        self.path = path
        self.legacy_instance = legacy_instance
        self.migrated_profile_id = ""
        if not self.path.exists():
            legacy_origin = self.legacy_instance.get()
            if legacy_origin:
                profile = RockProfile(
                    uuid.uuid4().hex,
                    default_profile_name(legacy_origin),
                    legacy_origin,
                )
                self._write(self._new_state(profile))
                self.migrated_profile_id = profile.profile_id

    def snapshot(self) -> dict[str, Any]:
        state = self._read()
        active = state["activeProfileId"]
        return {
            "activeProfileId": active,
            "profiles": [
                profile.public_dict(active) for profile in self._profiles(state)
            ],
            "preferences": dict(state["preferences"]),
        }

    def preferences(self) -> dict[str, Any]:
        return dict(self._read()["preferences"])

    def active(self) -> RockProfile | None:
        state = self._read()
        profile_id = state["activeProfileId"]
        return next(
            (profile for profile in self._profiles(state) if profile.profile_id == profile_id),
            None,
        )

    def get(self, profile_id: object) -> RockProfile:
        safe_id = validate_profile_id(profile_id)
        profile = next(
            (profile for profile in self._profiles(self._read()) if profile.profile_id == safe_id),
            None,
        )
        if profile is None:
            raise ProfileError("profile_not_found")
        return profile

    def add(self, name: object, origin: object) -> RockProfile:
        state = self._read()
        if len(state["profiles"]) >= MAX_PROFILES:
            raise ProfileError("profile_limit_reached")
        try:
            safe_origin = validate_rock_origin(origin)
        except OriginError as error:
            raise ProfileError("invalid_rock_origin") from error
        safe_name = self._name(name, safe_origin)
        profile = RockProfile(uuid.uuid4().hex, safe_name, safe_origin)
        state["profiles"].append(self._record(profile))
        state["activeProfileId"] = profile.profile_id
        self._write(state)
        self.legacy_instance.set(safe_origin)
        return profile

    def set_active(self, profile_id: object) -> RockProfile:
        profile = self.get(profile_id)
        state = self._read()
        state["activeProfileId"] = profile.profile_id
        self._write(state)
        self.legacy_instance.set(profile.origin)
        return profile

    def rename(self, profile_id: object, name: object) -> RockProfile:
        profile = self.get(profile_id)
        safe_name = self._name(name, profile.origin)
        state = self._read()
        for row in state["profiles"]:
            if row["id"] == profile.profile_id:
                row["name"] = safe_name
        self._write(state)
        return RockProfile(profile.profile_id, safe_name, profile.origin)

    def remove(self, profile_id: object) -> RockProfile:
        profile = self.get(profile_id)
        state = self._read()
        state["profiles"] = [
            row for row in state["profiles"] if row["id"] != profile.profile_id
        ]
        if state["activeProfileId"] == profile.profile_id:
            state["activeProfileId"] = (
                state["profiles"][0]["id"] if state["profiles"] else ""
            )
        self._write(state)
        active = self.active()
        if active:
            self.legacy_instance.set(active.origin)
        else:
            self.legacy_instance.clear()
        return profile

    def update_preferences(self, updates: object) -> dict[str, Any]:
        if not isinstance(updates, dict):
            raise ProfileError("invalid_preferences")
        allowed = set(DEFAULT_PREFERENCES)
        if not set(updates).issubset(allowed):
            raise ProfileError("invalid_preferences")
        state = self._read()
        preferences = dict(state["preferences"])
        for name in (
            "showPersonContext",
            "recentLinks",
            "closeAfterOpen",
            "automaticUpdates",
        ):
            if name in updates:
                if not isinstance(updates[name], bool):
                    raise ProfileError("invalid_preferences")
                preferences[name] = updates[name]
        if "enabledCategories" in updates:
            categories = updates["enabledCategories"]
            if (
                not isinstance(categories, list)
                or any(not isinstance(item, str) for item in categories)
                or len(categories) != len(set(categories))
                or not set(categories).issubset(CATEGORIES)
            ):
                raise ProfileError("invalid_preferences")
            preferences["enabledCategories"] = [
                category for category in CATEGORIES if category in categories
            ]
        state["preferences"] = preferences
        self._write(state)
        return dict(preferences)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._new_state()
        try:
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self.path, flags)
            try:
                info = os.fstat(descriptor)
                if (
                    info.st_uid != os.getuid()
                    or not stat.S_ISREG(info.st_mode)
                    or info.st_mode & 0o077
                    or info.st_size > MAX_PROFILE_STORE_BYTES
                ):
                    raise ProfileError("profile_store_unavailable")
                raw = os.read(descriptor, MAX_PROFILE_STORE_BYTES + 1)
            finally:
                os.close(descriptor)
            value = json.loads(raw)
            return self._validated_state(value)
        except ProfileError:
            raise
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            RecursionError,
        ) as error:
            raise ProfileError("profile_store_unavailable") from error

    def _write(self, state: dict[str, Any]) -> None:
        validated = self._validated_state(state)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path.parent.chmod(0o700)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".profiles-", dir=self.path.parent
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(validated, output, separators=(",", ":"), ensure_ascii=True)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
            self.path.chmod(0o600)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _record(profile: RockProfile) -> dict[str, str]:
        return {"id": profile.profile_id, "name": profile.name, "origin": profile.origin}

    @classmethod
    def _new_state(cls, profile: RockProfile | None = None) -> dict[str, Any]:
        return {
            "version": 1,
            "activeProfileId": profile.profile_id if profile else "",
            "profiles": [cls._record(profile)] if profile else [],
            "preferences": dict(DEFAULT_PREFERENCES),
        }

    @classmethod
    def _validated_state(cls, value: object) -> dict[str, Any]:
        if not isinstance(value, dict) or value.get("version") != 1:
            raise ProfileError("profile_store_unavailable")
        rows = value.get("profiles")
        active = value.get("activeProfileId")
        preferences = value.get("preferences")
        if (
            not isinstance(rows, list)
            or len(rows) > MAX_PROFILES
            or not isinstance(active, str)
            or not isinstance(preferences, dict)
        ):
            raise ProfileError("profile_store_unavailable")
        profiles: list[dict[str, str]] = []
        ids: set[str] = set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"id", "name", "origin"}:
                raise ProfileError("profile_store_unavailable")
            try:
                profile_id = validate_profile_id(row.get("id"))
                origin = validate_rock_origin(row.get("origin"))
            except (ProfileError, OriginError) as error:
                raise ProfileError("profile_store_unavailable") from error
            if not isinstance(row.get("name"), str):
                raise ProfileError("profile_store_unavailable")
            name = sanitize_text(row.get("name"), 80)
            if not name or profile_id in ids:
                raise ProfileError("profile_store_unavailable")
            ids.add(profile_id)
            profiles.append({"id": profile_id, "name": name, "origin": origin})
        if active and active not in ids:
            raise ProfileError("profile_store_unavailable")
        if profiles and not active:
            raise ProfileError("profile_store_unavailable")
        clean_preferences = dict(DEFAULT_PREFERENCES)
        for name in (
            "showPersonContext",
            "recentLinks",
            "closeAfterOpen",
            "automaticUpdates",
        ):
            candidate = preferences.get(name, clean_preferences[name])
            if not isinstance(candidate, bool):
                raise ProfileError("profile_store_unavailable")
            clean_preferences[name] = candidate
        categories = preferences.get("enabledCategories", list(CATEGORIES))
        if (
            not isinstance(categories, list)
            or any(not isinstance(item, str) for item in categories)
            or len(categories) != len(set(categories))
            or not set(categories).issubset(CATEGORIES)
        ):
            raise ProfileError("profile_store_unavailable")
        clean_preferences["enabledCategories"] = [
            category for category in CATEGORIES if category in categories
        ]
        return {
            "version": 1,
            "activeProfileId": active,
            "profiles": profiles,
            "preferences": clean_preferences,
        }

    @staticmethod
    def _profiles(state: dict[str, Any]) -> list[RockProfile]:
        return [
            RockProfile(row["id"], row["name"], row["origin"])
            for row in state["profiles"]
        ]

    @staticmethod
    def _name(value: object, origin: str) -> str:
        if value is not None and not isinstance(value, str):
            raise ProfileError("invalid_profile_name")
        name = sanitize_text(value, 80)
        if not name:
            name = default_profile_name(origin)
        if not name or any(ord(char) < 32 for char in name):
            raise ProfileError("invalid_profile_name")
        return name

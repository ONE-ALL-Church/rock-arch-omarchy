from __future__ import annotations

from pathlib import Path
from typing import Any

from .auth import AuthState, ConfigStore, OAuthManager, default_config_path
from .contracts import Capability, Context, HealthState, sanitize_text
from .mock_adapter import MockAdapter


class Broker:
    def __init__(
        self,
        state_file: Path | None = None,
        auth: OAuthManager | None = None,
        config_file: Path | None = None,
    ) -> None:
        self._state_file = state_file
        self._context = self._load_context()
        self._mock = MockAdapter()
        self._auth = auth or OAuthManager(
            ConfigStore(config_file or default_config_path())
        )
        self._store_context()

    def _load_context(self) -> Context:
        if self._state_file:
            try:
                value = self._state_file.read_text(encoding="utf-8").strip()
                return Context(value)
            except (OSError, ValueError):
                pass
        return Context.DEV

    def _store_context(self) -> None:
        if not self._state_file:
            return
        self._state_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._state_file.write_text(self._context.value + "\n", encoding="utf-8")
        self._state_file.chmod(0o600)

    def capabilities(self, auth: dict[str, Any] | None = None) -> list[dict[str, str]]:
        auth = auth or self._auth.public_status(self._context)
        oauth_state = AuthState(auth["state"])
        oauth_health = (
            HealthState.HEALTHY
            if oauth_state is AuthState.AUTHENTICATED
            else HealthState.UNKNOWN
        )
        if oauth_state is AuthState.FAILED:
            oauth_health = HealthState.FAILED
        elif oauth_state is AuthState.EXPIRED:
            oauth_health = HealthState.STALE
        return [
            Capability(
                "mock", HealthState.HEALTHY, "Synthetic data enabled"
            ).public_dict(),
            Capability("rock_oauth", oauth_health, auth["label"]).public_dict(),
            Capability(
                "rock_v3", HealthState.UNKNOWN, "Live adapter gated"
            ).public_dict(),
            Capability(
                "sql", HealthState.UNKNOWN, "Read-only identity unproven"
            ).public_dict(),
            Capability(
                "magnus", HealthState.UNKNOWN, "Capability unavailable"
            ).public_dict(),
        ]

    def handle(self, raw: dict[str, Any]) -> dict[str, Any]:
        op = sanitize_text(raw.get("op"), 40)
        if op == "status":
            auth = self._auth.public_status(self._context)
            return self._ok(
                context=self._context.value,
                auth=auth,
                capabilities=self.capabilities(auth),
                categories=list(self._mock.categories()),
            )
        if op == "set_context":
            try:
                self._context = Context(sanitize_text(raw.get("context"), 8))
            except ValueError:
                return self._error("invalid_context")
            self._store_context()
            return self._ok(
                context=self._context.value,
                auth=self._auth.public_status(self._context),
            )
        if op == "auth_status":
            return self._ok(auth=self._auth.public_status(self._context))
        if op == "auth_login":
            return self._ok(auth=self._auth.begin_login(self._context))
        if op == "auth_disconnect":
            return self._ok(auth=self._auth.disconnect(self._context))
        if op == "search":
            query = sanitize_text(raw.get("query"), 120)
            return self._ok(
                context=self._context.value, results=self._mock.search(query)
            )
        if op == "person_quick_look":
            person = self._mock.person_quick_look(sanitize_text(raw.get("safeId"), 80))
            return self._ok(person=person) if person else self._error("not_found")
        return self._error("unsupported_operation")

    @staticmethod
    def _ok(**payload: Any) -> dict[str, Any]:
        return {"ok": True, **payload}

    @staticmethod
    def _error(code: str) -> dict[str, Any]:
        return {"ok": False, "error": code}

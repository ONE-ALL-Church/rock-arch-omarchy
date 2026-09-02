from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Protocol

from .auth import AuthState, ConfigStore, OAuthManager, default_config_path
from .contracts import (
    CATEGORIES,
    Capability,
    Context,
    HealthState,
    parse_search_query,
    sanitize_text,
)
from .instance import InstanceStore, default_instance_path
from .magnus_adapter import MagnusError, MagnusReadOnlyAdapter
from .mock_adapter import MockAdapter
from .navigation import NavigationTarget, open_rock_url
from .origin import DEFAULT_ROCK_ORIGIN, OriginError
from .quick_return import QuickReturnStore
from .rock_rest_adapter import RockRestError, RockRestReadOnlyAdapter, SearchBatch


class MagnusStatusProvider(Protocol):
    def status(self) -> dict[str, Any]: ...

    def authenticated_cookie(self) -> AbstractContextManager[str]: ...

    def configure(self, username: str, password: str) -> None: ...

    def set_server(self, value: str) -> None: ...


class LiveReadAdapter(Protocol):
    def clear(self) -> None: ...

    def search(self, query: str, category: str | None = None) -> SearchBatch: ...

    def person_quick_look(self, safe_id: str) -> dict[str, Any] | None: ...

    def personal_links(self) -> list[dict[str, Any]]: ...

    def resolve(self, safe_id: str) -> NavigationTarget | None: ...

    def set_origin(self, origin: str) -> None: ...


class Broker:
    def __init__(
        self,
        state_file: Path | None = None,
        auth: OAuthManager | None = None,
        config_file: Path | None = None,
        magnus: MagnusStatusProvider | None = None,
        live: LiveReadAdapter | None = None,
        quick_returns: QuickReturnStore | None = None,
        url_opener: Callable[[str], bool] | None = None,
        instance_file: Path | None = None,
    ) -> None:
        self._state_file = state_file
        self._context = self._load_context()
        self._mock = MockAdapter()
        instance_path = instance_file or (
            config_file.with_name("instance.json")
            if config_file
            else default_instance_path()
        )
        self._instance_store = InstanceStore(instance_path)
        self._origin = self._instance_store.get()
        self._magnus = magnus or MagnusReadOnlyAdapter(server=self._origin)
        if magnus and self._origin:
            self._magnus.set_server(self._origin)
        self._live = live or RockRestReadOnlyAdapter(
            self._magnus, origin=self._origin or DEFAULT_ROCK_ORIGIN
        )
        if live and self._origin:
            self._live.set_origin(self._origin)
        self._quick_root = (
            state_file.parent
            if state_file
            else Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
            / "rock-lens"
        )
        self._quick_returns_injected = quick_returns is not None
        self._quick_returns = quick_returns or QuickReturnStore(
            self._quick_return_path(), self._origin
        )
        if quick_returns and self._origin:
            self._quick_returns.set_origin(self._origin)
        self._url_opener = url_opener
        self._live_health = HealthState.UNKNOWN
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

    def capabilities(
        self,
        auth: dict[str, Any] | None = None,
        magnus: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
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
        magnus = magnus or self._magnus.status()
        magnus_detail = (
            "Secure read-only adapter configured"
            if magnus["configured"]
            else "Secure login required"
        )
        return [
            Capability(
                "mock", HealthState.HEALTHY, "Synthetic data enabled"
            ).public_dict(),
            Capability("rock_oauth", oauth_health, auth["label"]).public_dict(),
            Capability(
                "rock_rest", self._live_health, "Allowlisted GETs only"
            ).public_dict(),
            Capability(
                "sql", HealthState.UNKNOWN, "Read-only identity unproven"
            ).public_dict(),
            Capability("magnus", HealthState.UNKNOWN, magnus_detail).public_dict(),
        ]

    def handle(self, raw: dict[str, Any]) -> dict[str, Any]:
        op = sanitize_text(raw.get("op"), 40)
        if op == "status":
            auth = self._auth.public_status(self._context)
            magnus = self._magnus.status()
            return self._ok(
                context=self._context.value,
                auth=auth,
                instance=self._instance_status(),
                magnus=magnus,
                capabilities=self.capabilities(auth, magnus),
                categories=list(self._mock.categories()),
            )
        if op == "set_context":
            try:
                self._context = Context(sanitize_text(raw.get("context"), 8))
            except ValueError:
                return self._error("invalid_context")
            self._store_context()
            self._live.clear()
            return self._ok(
                context=self._context.value,
                auth=self._auth.public_status(self._context),
                instance=self._instance_status(),
                magnus=self._magnus.status(),
            )
        if op == "auth_status":
            return self._ok(auth=self._auth.public_status(self._context))
        if op == "auth_login":
            return self._ok(auth=self._auth.begin_login(self._context))
        if op == "auth_disconnect":
            return self._ok(auth=self._auth.disconnect(self._context))
        if op == "magnus_status":
            return self._ok(magnus=self._magnus.status())
        if op == "magnus_configure":
            domain = raw.get("domain")
            username = raw.get("username")
            password = raw.get("password")
            if (
                not isinstance(domain, str)
                or not isinstance(username, str)
                or not isinstance(password, str)
            ):
                return self._error("invalid_magnus_credentials")
            try:
                origin = self._instance_store.set(domain)
                self._set_origin(origin)
                self._magnus.configure(username, password)
            except OriginError:
                return self._error("invalid_rock_origin")
            except MagnusError as error:
                return self._error(str(error))
            self._live.clear()
            return self._ok(
                instance=self._instance_status(),
                magnus=self._magnus.status(),
                refreshLive=True,
            )
        if op == "search":
            query, category = parse_search_query(raw.get("query"))
            unavailable_categories = [category] if category else list(CATEGORIES)
            if self._context is Context.DEV:
                return self._ok(
                    context=self._context.value,
                    results=self._mock.search(query, category=category),
                    source="synthetic",
                    unavailable=[],
                )
            if not self._origin or not self._magnus.status()["configured"]:
                return self._ok(
                    context=self._context.value,
                    results=[],
                    source="unavailable",
                    unavailable=unavailable_categories,
                )
            if not query and category is None:
                return self._ok(
                    context=self._context.value,
                    results=[],
                    source="live",
                    unavailable=[],
                )
            try:
                batch = self._live.search(query, category)
            except RockRestError:
                self._live_health = HealthState.FAILED
                return self._ok(
                    context=self._context.value,
                    results=[],
                    source="unavailable",
                    unavailable=unavailable_categories,
                )
            self._live_health = (
                HealthState.STALE if batch.unavailable else HealthState.HEALTHY
            )
            return self._ok(
                context=self._context.value,
                results=batch.results,
                source="live",
                unavailable=list(batch.unavailable),
            )
        if op == "person_quick_look":
            safe_id = sanitize_text(raw.get("safeId"), 100)
            person = (
                self._mock.person_quick_look(safe_id)
                if self._context is Context.DEV
                else self._live.person_quick_look(safe_id)
            )
            return self._ok(person=person) if person else self._error("not_found")
        if op == "navigation_status":
            section = raw.get("section", "all")
            if not isinstance(section, str) or section not in {
                "all",
                "personal",
                "quick_returns",
            }:
                return self._error("invalid_navigation_section")
            return self._navigation_status(section)
        if op == "open_navigation":
            return self._open_navigation(sanitize_text(raw.get("safeId"), 100))
        return self._error("unsupported_operation")

    def _navigation_status(self, section: str) -> dict[str, Any]:
        response: dict[str, Any] = {}
        if section in {"all", "personal"}:
            personal_links: list[dict[str, Any]] = []
            available = False
            if (
                self._context is Context.PROD
                and self._origin
                and self._magnus.status()["configured"]
            ):
                try:
                    personal_links = self._live.personal_links()
                    self._live_health = HealthState.HEALTHY
                    available = True
                except RockRestError:
                    self._live_health = HealthState.STALE
            response.update(
                personalLinks=personal_links,
                personalLinksAvailable=available,
            )
        if section in {"all", "quick_returns"}:
            response["quickReturns"] = (
                self._quick_returns.public_items()
                if self._context is Context.PROD
                else []
            )
        return self._ok(**response)

    def _open_navigation(self, safe_id: str) -> dict[str, Any]:
        if self._context is not Context.PROD:
            return self._error("navigation_requires_prod")
        target = self._live.resolve(safe_id) or self._quick_returns.resolve(safe_id)
        if not isinstance(target, NavigationTarget):
            return self._error("not_found")
        opened = (
            self._url_opener(target.url)
            if self._url_opener
            else bool(self._origin and open_rock_url(target.url, self._origin))
        )
        if not opened:
            return self._error("open_failed")
        self._quick_returns.add(target)
        return self._ok(opened=True, quickReturns=self._quick_returns.public_items())

    def _set_origin(self, origin: str) -> None:
        self._origin = origin
        self._magnus.set_server(origin)
        self._live.set_origin(origin)
        if self._quick_returns_injected:
            self._quick_returns.set_origin(origin)
        else:
            self._quick_returns = QuickReturnStore(self._quick_return_path(), origin)
        self._live_health = HealthState.UNKNOWN

    def _quick_return_path(self) -> Path:
        key = (
            hashlib.sha256(self._origin.encode()).hexdigest()[:16]
            if self._origin
            else "unconfigured"
        )
        return self._quick_root / f"quick-returns-{key}.json"

    def _instance_status(self) -> dict[str, Any]:
        return {
            "configured": bool(self._origin),
            "origin": self._origin or "",
        }

    @staticmethod
    def _ok(**payload: Any) -> dict[str, Any]:
        return {"ok": True, **payload}

    @staticmethod
    def _error(code: str) -> dict[str, Any]:
        return {"ok": False, "error": code}

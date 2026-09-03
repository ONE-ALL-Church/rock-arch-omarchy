from __future__ import annotations

import hashlib
import os
import threading
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Protocol

from .broker_operations import BrokerOperations
from .build_receipts import BuildReceiptStore
from .clipboard import copy_to_clipboard
from .contracts import (
    ALLOWED_RESULT_KEYS,
    Capability,
    Context,
    HealthState,
    allowlist,
    developer_mode_enabled,
    sanitize_text,
)
from .instance import InstanceStore, default_instance_path
from .magnus_adapter import MagnusBuildOutcome, MagnusError, MagnusReadOnlyAdapter
from .mock_adapter import MockAdapter
from .navigation import NavigationTarget, open_rock_url
from .notifications import notify_build_accepted
from .origin import DEFAULT_ROCK_ORIGIN
from .profiles import ProfileError, ProfileStore, RockProfile
from .quick_return import QuickReturnStore
from .rock_kb_adapter import (
    RockKbError,
    RockKbReadOnlyAdapter,
    open_public_source_url,
    validate_public_source_url,
)
from .rock_rest_adapter import (
    RockRestError,
    RockRestReadOnlyAdapter,
    SearchBatch,
    SearchCapabilities,
)
from .rock_session import RockSessionError, RockSessionProvider
from .terminal_access import UnmanagedTerminalAccess
from .updates import UpdateManager


class RockSessionStatusProvider(Protocol):
    def status(self) -> dict[str, Any]: ...

    def authenticated_cookie(self) -> AbstractContextManager[str]: ...

    def invalidate_authenticated_cookie(self) -> None: ...

    def configure(self, username: str, password: str) -> None: ...

    def set_server(self, value: str) -> None: ...

    def set_profile(self, profile_id: str, server: str) -> None: ...

    def clear_profile(self) -> None: ...

    def migrate_legacy_credentials(self) -> bool: ...

    def sign_out(self) -> None: ...

    def remove_profile_credentials(self, profile_id: str) -> None: ...

    def test_connection(self) -> None: ...


class MagnusStatusProvider(Protocol):
    def status(self) -> dict[str, Any]: ...

    def set_server(self, value: str) -> None: ...

    def set_profile(self, profile_id: str, server: str) -> None: ...

    def clear_profile(self) -> None: ...

    def probe(self) -> bool: ...

    def browse(self, safe_id: str = "") -> dict[str, Any]: ...

    def preview(self, safe_id: str) -> dict[str, Any]: ...

    def download(self, safe_id: str) -> dict[str, Any]: ...

    def file_hash(self, safe_id: str) -> dict[str, Any]: ...

    def copy_value(self, safe_id: str, value: str) -> str: ...

    def view_target(self, safe_id: str) -> NavigationTarget: ...

    def build(self, safe_id: str) -> MagnusBuildOutcome: ...

    def build_recent(self, url: str, title: str) -> MagnusBuildOutcome: ...

    def describe(self, safe_id: str) -> dict[str, Any]: ...


class LiveReadAdapter(Protocol):
    def clear(self) -> None: ...

    def searchable_categories(
        self, force_refresh: bool = False
    ) -> SearchCapabilities: ...

    def search(
        self,
        query: str,
        category: str | None = None,
        categories: list[str] | None = None,
        include_person_context: bool = True,
    ) -> SearchBatch: ...

    def person_quick_look(self, safe_id: str) -> dict[str, Any] | None: ...

    def personal_links(self, force_refresh: bool = False) -> list[dict[str, Any]]: ...

    def resolve(self, safe_id: str) -> NavigationTarget | None: ...

    def set_origin(self, origin: str) -> None: ...


class KnowledgeProvider(Protocol):
    def search(self, query: str) -> list[dict[str, Any]]: ...

    def detail(self, safe_id: str) -> dict[str, Any]: ...

    def source_url(self, safe_id: str) -> str | None: ...

    def describe(self, safe_id: str) -> dict[str, Any]: ...


class UpdateStatusProvider(Protocol):
    def status(
        self, *, refresh: bool = False, automatic_install: bool = False
    ) -> dict[str, Any]: ...

    def start_update(self) -> dict[str, Any]: ...


class TerminalAccessProvider(Protocol):
    def ensure_launcher(self) -> None: ...

    def status(self, *, enabled: bool) -> dict[str, Any]: ...


class Broker:
    def __init__(
        self,
        state_file: Path | None = None,
        session: RockSessionStatusProvider | None = None,
        magnus: MagnusStatusProvider | None = None,
        live: LiveReadAdapter | None = None,
        knowledge: KnowledgeProvider | None = None,
        quick_returns: QuickReturnStore | None = None,
        build_receipts: BuildReceiptStore | None = None,
        build_notifier: Callable[[], bool] | None = None,
        url_opener: Callable[[str], bool] | None = None,
        clipboard_writer: Callable[[str], bool] | None = None,
        instance_file: Path | None = None,
        profile_file: Path | None = None,
        developer_mode: bool | None = None,
        updates: UpdateStatusProvider | None = None,
        terminal_access: TerminalAccessProvider | None = None,
    ) -> None:
        self._state_file = state_file
        self._developer_mode = (
            developer_mode_enabled() if developer_mode is None else developer_mode
        )
        self._context = self._load_context()
        self._mock = MockAdapter()
        instance_path = instance_file or default_instance_path()
        self._instance_store = InstanceStore(instance_path)
        self._profile_store = ProfileStore(
            profile_file or instance_path.with_name("profiles.json"),
            self._instance_store,
        )
        active_profile = self._profile_store.active()
        self._active_profile_id = active_profile.profile_id if active_profile else ""
        self._origin = active_profile.origin if active_profile else None
        self._session = session or RockSessionProvider(
            origin=self._origin,
            profile_id=self._active_profile_id or None,
        )
        if session and active_profile:
            self._session.set_profile(active_profile.profile_id, active_profile.origin)
        if active_profile:
            migrate = getattr(self._session, "migrate_legacy_credentials", None)
            if callable(migrate):
                try:
                    migrate()
                except RockSessionError:
                    pass
        self._magnus = magnus or MagnusReadOnlyAdapter(
            self._session, server=self._origin
        )
        if magnus and active_profile:
            self._magnus.set_profile(active_profile.profile_id, active_profile.origin)
        self._live = live or RockRestReadOnlyAdapter(
            self._session, origin=self._origin or DEFAULT_ROCK_ORIGIN
        )
        if live and self._origin:
            self._live.set_origin(self._origin)
        self._knowledge = knowledge or RockKbReadOnlyAdapter()
        self._quick_root = (
            state_file.parent
            if state_file
            else Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
            / "rock-arch"
        )
        self._quick_returns_injected = quick_returns is not None
        self._quick_returns = quick_returns or QuickReturnStore(
            self._quick_return_path(), self._origin
        )
        self._build_receipts_injected = build_receipts is not None
        self._build_receipts = build_receipts or BuildReceiptStore(
            self._build_receipt_path()
        )
        self._build_notifier = build_notifier or notify_build_accepted
        self._updates = updates or UpdateManager(self._quick_root / "updates.json")
        self._terminal_access = terminal_access or UnmanagedTerminalAccess()
        self._terminal_access.ensure_launcher()
        if (
            not quick_returns
            and self._profile_store.migrated_profile_id
            and self._origin
        ):
            self._quick_returns.migrate_from(
                self._legacy_quick_return_path(self._origin)
            )
        if quick_returns and self._origin:
            self._quick_returns.set_origin(self._origin)
        self._url_opener = url_opener
        self._clipboard_writer = clipboard_writer or copy_to_clipboard
        self._live_health = HealthState.UNKNOWN
        self._pending_ui_handoff: dict[str, Any] | None = None
        self._pending_ui_handoff_deadline = 0.0
        self._ui_handoff_lock = threading.Lock()
        self._ui_handoff_timer: threading.Timer | None = None
        self._operations = BrokerOperations(self)
        self._store_context()

    def _load_context(self) -> Context:
        if not self._developer_mode:
            return Context.PROD
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
        rock: dict[str, Any] | None = None,
        magnus: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        rock = rock or self._session.status()
        magnus = magnus or self._magnus.status()
        rock_health = HealthState.HEALTHY if rock["configured"] else HealthState.UNKNOWN
        magnus_state = magnus.get("state", "unknown")
        magnus_health = (
            HealthState.HEALTHY
            if magnus_state == "available"
            else HealthState.FAILED
            if magnus_state == "error"
            else HealthState.UNKNOWN
        )
        magnus_detail = {
            "available": "Browse, preview, and hash available",
            "unavailable": "Not installed or not authorized",
            "error": "Capability check could not complete",
            "signed_out": "Rock login required",
        }.get(magnus_state, "Capability not checked")
        if self._context is Context.DEV:
            magnus_detail = "Preview files and build confirmation"
        return [
            Capability(
                "mock",
                HealthState.HEALTHY if self._developer_mode else HealthState.UNKNOWN,
                (
                    "Synthetic data enabled"
                    if self._developer_mode
                    else "Developer mode disabled"
                ),
            ).public_dict(),
            Capability(
                "rock_session",
                rock_health,
                "Native Rock login" if rock["configured"] else "Rock login required",
            ).public_dict(),
            Capability(
                "rock_rest", self._live_health, "Allowlisted GETs only"
            ).public_dict(),
            Capability(
                "sql", HealthState.UNKNOWN, "Read-only identity unproven"
            ).public_dict(),
            Capability("magnus", magnus_health, magnus_detail).public_dict(),
        ]

    def handle(self, raw: dict[str, Any]) -> dict[str, Any]:
        return self._operations.handle(raw)

    def _navigation_status(self, section: str) -> dict[str, Any]:
        response: dict[str, Any] = {}
        if self._context is Context.DEV:
            if section in {"all", "personal"}:
                response.update(
                    personalLinks=self._mock.personal_links(),
                    personalLinksAvailable=True,
                )
            if section in {"all", "quick_returns"}:
                response["quickReturns"] = self._mock.quick_returns()
            return self._ok(**response)
        if section in {"all", "personal"}:
            personal_links: list[dict[str, Any]] = []
            available = False
            if (
                self._context is Context.PROD
                and self._origin
                and self._session.status()["configured"]
            ):
                try:
                    personal_links = self._live.personal_links(force_refresh=True)
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
                and self._profile_store.preferences()["recentLinks"]
                else []
            )
        return self._ok(**response)

    @staticmethod
    def _matching_personal_links(
        query: str, links: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        terms = sanitize_text(query, 120).casefold().split()
        if not terms:
            return []
        matches: list[tuple[int, int, dict[str, Any]]] = []
        for index, link in enumerate(links):
            title = sanitize_text(link.get("title"), 160)
            section = sanitize_text(link.get("section"), 120)
            title_folded = title.casefold()
            haystack = f"{title} {section}".casefold()
            if not title or not all(term in haystack for term in terms):
                continue
            phrase = " ".join(terms)
            rank = (
                0
                if title_folded == phrase
                else 1
                if title_folded.startswith(phrase)
                else 2
                if all(term in title_folded for term in terms)
                else 3
            )
            matches.append(
                (
                    rank,
                    index,
                    allowlist(
                        {
                            "category": "Personal Links",
                            "safeId": link.get("safeId"),
                            "title": title,
                            "subtitle": section or "Rock bookmark",
                            "status": "Shared" if link.get("isShared") else "Personal",
                            "canOpen": True,
                        },
                        ALLOWED_RESULT_KEYS,
                    ),
                )
            )
        matches.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in matches]

    def _open_navigation(self, safe_id: str) -> dict[str, Any]:
        if self._context is not Context.PROD:
            return (
                self._ok(previewAction="Preview only · no Rock page was opened")
                if self._mock.has_navigation_item(safe_id)
                else self._error("not_found")
            )
        target = self._live.resolve(safe_id) or self._quick_returns.resolve(safe_id)
        if not isinstance(target, NavigationTarget):
            return self._error("not_found")
        if target.kind == "Magnus Build":
            return self._error("build_confirmation_required")
        return self._open_target(target)

    def _knowledge_detail(self, safe_id: str) -> dict[str, Any]:
        try:
            detail = self._knowledge.detail(safe_id)
        except RockKbError as error:
            return self._error(str(error))
        return self._ok(knowledgeDetail=detail)

    def _open_knowledge_source(self, safe_id: str) -> dict[str, Any]:
        source_url = self._knowledge.source_url(safe_id)
        if not source_url:
            return self._error("knowledge_source_not_found")
        try:
            source_url = validate_public_source_url(source_url)
        except RockKbError:
            return self._error("knowledge_source_not_found")
        opened = (
            self._url_opener(source_url)
            if self._url_opener
            else open_public_source_url(source_url)
        )
        if not opened:
            return self._error("open_failed")
        return self._ok(knowledgeOpened=True)

    def _open_target(self, target: NavigationTarget) -> dict[str, Any]:
        opened = (
            self._url_opener(target.url)
            if self._url_opener
            else bool(self._origin and open_rock_url(target.url, self._origin))
        )
        if not opened:
            return self._error("open_failed")
        recent_links_enabled = self._profile_store.preferences()["recentLinks"]
        if recent_links_enabled:
            self._quick_returns.add(target)
        return self._ok(
            opened=True,
            quickReturns=(
                self._quick_returns.public_items() if recent_links_enabled else []
            ),
        )

    def _activate_recent(self, safe_id: str, confirmed: bool = False) -> dict[str, Any]:
        if self._context is not Context.PROD:
            if not self._mock.has_navigation_item(safe_id):
                return self._error("not_found")
            if self._mock.is_recent_build(safe_id):
                if not confirmed:
                    return self._error("build_confirmation_required")
                return self._ok(
                    magnusBuild={
                        "title": "Weekend Mobile",
                        "message": "Preview complete · no deployment was started",
                        "previewOnly": True,
                    },
                    magnusBuilds=self._mock.magnus_builds(),
                    quickReturns=self._mock.quick_returns(),
                )
            return self._ok(previewAction="Preview only · no Rock page was opened")
        target = self._quick_returns.resolve(safe_id)
        if not isinstance(target, NavigationTarget):
            return self._error("not_found")
        if target.kind != "Magnus Build":
            return self._open_target(target)
        if not confirmed:
            return self._error("build_confirmation_required")
        try:
            outcome = self._magnus.build_recent(
                target.url, target.title.removeprefix("Deploy ")
            )
        except MagnusError as error:
            return self._error(str(error))
        return self._complete_build(outcome)

    def _complete_build(self, outcome: MagnusBuildOutcome) -> dict[str, Any]:
        recent_links_enabled = self._profile_store.preferences()["recentLinks"]
        if recent_links_enabled:
            self._quick_returns.add(outcome.target)
        receipt = self._build_receipts.add(outcome.title)
        notification_sent = self._build_notifier()
        return self._ok(
            magnusBuild={**outcome.public_dict(), **receipt},
            magnusBuildStatus=receipt,
            magnusBuilds=self._build_receipts.public_items(),
            notificationSent=notification_sent,
            quickReturns=(
                self._quick_returns.public_items() if recent_links_enabled else []
            ),
        )

    def _activate_profile(self, profile: RockProfile | None) -> None:
        if profile is None:
            self._active_profile_id = ""
            self._origin = None
            self._session.clear_profile()
            self._magnus.clear_profile()
            self._live.clear()
            self._quick_returns = QuickReturnStore(
                self._quick_root / "quick-returns-unconfigured.json"
            )
            if not self._build_receipts_injected:
                self._build_receipts = BuildReceiptStore(self._build_receipt_path())
            self._live_health = HealthState.UNKNOWN
            return
        self._active_profile_id = profile.profile_id
        self._origin = profile.origin
        self._session.set_profile(profile.profile_id, profile.origin)
        self._magnus.set_profile(profile.profile_id, profile.origin)
        self._live.set_origin(profile.origin)
        if self._quick_returns_injected:
            self._quick_returns.set_origin(profile.origin)
        else:
            self._quick_returns = QuickReturnStore(
                self._quick_return_path(), profile.origin
            )
        if not self._build_receipts_injected:
            self._build_receipts = BuildReceiptStore(self._build_receipt_path())
        self._live_health = HealthState.UNKNOWN

    def _profile_response(self, **payload: Any) -> dict[str, Any]:
        preferences = self._profile_store.preferences()
        return self._ok(
            profiles=self._profile_store.snapshot(),
            instance=self._instance_status(),
            rock=self._session.status(),
            magnus=self._magnus.status(),
            terminal=self._terminal_access.status(
                enabled=preferences["terminalAccess"]
            ),
            magnusBuilds=self._build_receipts.public_items(),
            **payload,
        )

    def _profile_add(self, raw: dict[str, Any]) -> dict[str, Any]:
        username = raw.get("username")
        password = raw.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            return self._error("invalid_rock_credentials")
        previous = self._profile_store.active()
        added: RockProfile | None = None
        try:
            added = self._profile_store.add(raw.get("name"), raw.get("domain"))
            self._activate_profile(added)
            self._session.configure(username, password)
            self._reset_magnus_access()
        except (ProfileError, RockSessionError) as error:
            if added and not self._rollback_profile_add(added, previous):
                return self._error("secure_storage_failed")
            return self._error(str(error))
        self._live.clear()
        return self._profile_response(refreshLive=True)

    def _rollback_profile_add(
        self,
        added: RockProfile,
        previous: RockProfile | None = None,
    ) -> bool:
        remover = getattr(self._session, "remove_profile_credentials", None)
        if callable(remover):
            try:
                remover(added.profile_id)
            except RockSessionError:
                # Keep the profile visible so the user can retry removal. Its
                # credentials may still exist in Secret Service.
                return False
        try:
            self._profile_store.remove(added.profile_id)
            if previous:
                self._profile_store.set_active(previous.profile_id)
        except ProfileError:
            return False
        self._activate_profile(previous)
        return True

    def _profile_remove(self, profile_id: object) -> dict[str, Any]:
        try:
            profile = self._profile_store.get(profile_id)
            remover = getattr(self._session, "remove_profile_credentials", None)
            if callable(remover):
                remover(profile.profile_id)
            path = self._quick_return_path(profile.profile_id)
            if not QuickReturnStore(path, profile.origin).clear():
                return self._error("recent_links_clear_failed")
            if not BuildReceiptStore(
                self._build_receipt_path(profile.profile_id)
            ).clear():
                return self._error("build_receipts_clear_failed")
            self._profile_store.remove(profile.profile_id)
            if profile.profile_id == self._active_profile_id:
                self._activate_profile(self._profile_store.active())
        except (ProfileError, RockSessionError, MagnusError) as error:
            return self._error(str(error))
        return self._profile_response(refreshLive=True)

    def _reset_magnus_access(self) -> None:
        resetter = getattr(self._magnus, "reset_access", None)
        if callable(resetter):
            resetter()

    def _probe_magnus(self, force: bool = False) -> None:
        if (
            self._context is not Context.PROD
            or not self._session.status()["configured"]
        ):
            return
        state = self._magnus.status().get("state", "unknown")
        if not force and state not in {"unknown", "error"}:
            return
        self._magnus.probe()

    def _quick_return_path(self, profile_id: str | None = None) -> Path:
        key = profile_id or self._active_profile_id or "unconfigured"
        return self._quick_root / f"quick-returns-{key}.json"

    def _build_receipt_path(self, profile_id: str | None = None) -> Path:
        key = profile_id or self._active_profile_id or "unconfigured"
        return self._quick_root / f"build-receipts-{key}.json"

    def _describe_safe_id(self, safe_id: str) -> dict[str, Any]:
        candidate = sanitize_text(safe_id, 100)
        if candidate.startswith("magnus-"):
            try:
                return self._magnus.describe(candidate)
            except MagnusError:
                raise ValueError("not_found") from None
        if candidate.startswith("kb-"):
            try:
                return self._knowledge.describe(candidate)
            except RockKbError:
                raise ValueError("not_found") from None
        target = self._live.resolve(candidate) or self._quick_returns.resolve(candidate)
        if target is None:
            raise ValueError("not_found")
        action = "build" if target.kind == "Magnus Build" else "open"
        return {
            "safeId": candidate,
            "title": target.title,
            "kind": target.kind,
            "actions": [action],
            "expires": "broker_restart",
        }

    def _set_ui_handoff(self, view: object, query: object) -> dict[str, Any]:
        clean_view = sanitize_text(view, 20) or "search"
        if clean_view not in {"search", "links", "knowledge", "magnus", "settings"}:
            raise ValueError("invalid_ui_view")
        clean_query = sanitize_text(query, 120)
        if clean_view not in {"search", "knowledge"} and clean_query:
            raise ValueError("invalid_ui_query")
        with self._ui_handoff_lock:
            if self._ui_handoff_timer:
                self._ui_handoff_timer.cancel()
            self._pending_ui_handoff = {"view": clean_view, "query": clean_query}
            self._pending_ui_handoff_deadline = time.monotonic() + 30.0
            self._ui_handoff_timer = threading.Timer(30.0, self._expire_ui_handoff)
            self._ui_handoff_timer.daemon = True
            self._ui_handoff_timer.start()
        return {"view": clean_view, "queryPending": bool(clean_query)}

    def _take_ui_handoff(self) -> dict[str, Any] | None:
        with self._ui_handoff_lock:
            handoff = self._pending_ui_handoff
            self._pending_ui_handoff = None
            deadline = self._pending_ui_handoff_deadline
            self._pending_ui_handoff_deadline = 0.0
            if self._ui_handoff_timer:
                self._ui_handoff_timer.cancel()
                self._ui_handoff_timer = None
        if not handoff or time.monotonic() > deadline:
            return None
        return handoff

    def _expire_ui_handoff(self) -> None:
        with self._ui_handoff_lock:
            self._pending_ui_handoff = None
            self._pending_ui_handoff_deadline = 0.0
            self._ui_handoff_timer = None

    def _legacy_quick_return_path(self, origin: str) -> Path:
        key = hashlib.sha256(origin.encode()).hexdigest()[:16]
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

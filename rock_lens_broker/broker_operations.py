from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .contracts import (
    CATEGORIES,
    KNOWLEDGE_CATEGORY,
    Context,
    HealthState,
    parse_search_query,
    sanitize_text,
)
from .magnus_adapter import MagnusError
from .origin import OriginError, validate_rock_origin
from .profiles import ProfileError, RockProfile, default_profile_name
from .rock_kb_adapter import RockKbError
from .rock_rest_adapter import RockRestError
from .rock_session import RockSessionError
from .terminal_access import CLI_CLIENT
from .updates import UpdateError

if TYPE_CHECKING:
    from .broker import Broker

OperationHandler = Callable[[dict[str, Any]], dict[str, Any]]


class BrokerOperations:
    """Request routing kept separate from broker state and lifecycle wiring."""

    def __init__(self, broker: Broker) -> None:
        self.broker = broker
        self._handlers: dict[str, OperationHandler] = {
            "status": self._status,
            "doctor": self._doctor,
            "describe": self._describe,
            "action_preview": self._action_preview,
            "ui_handoff_set": self._ui_handoff_set,
            "ui_handoff_take": self._ui_handoff_take,
            "set_context": self._set_context,
            "magnus_status": self._magnus_status,
            "search_capabilities": self._search_capabilities,
            "rock_configure": self._rock_configure,
            "magnus_configure": self._rock_configure,
            "profiles_status": self._profiles_status,
            "profile_add": self._profile_add,
            "profile_switch": self._profile_switch,
            "profile_rename": self._profile_rename,
            "profile_credentials_update": self._profile_credentials_update,
            "profile_test": self._profile_test,
            "profile_sign_out": self._profile_sign_out,
            "profile_remove": self._profile_remove,
            "preferences_update": self._preferences_update,
            "onboarding_setup_complete": self._onboarding_setup_complete,
            "update_status": self._update_status,
            "update_check": self._update_check,
            "update_start": self._update_start,
            "recent_links_clear": self._recent_links_clear,
            "magnus_browse": self._magnus_browse,
            "magnus_preview": self._magnus_preview,
            "magnus_download": self._magnus_download,
            "magnus_hash": self._magnus_hash,
            "magnus_copy": self._magnus_copy,
            "magnus_open": self._magnus_open,
            "magnus_build": self._magnus_build,
            "magnus_builds": self._magnus_builds,
            "magnus_build_status": self._magnus_build_status,
            "search": self._search,
            "knowledge_search": self._knowledge_search,
            "knowledge_result": self._knowledge_result,
            "knowledge_open_source": self._knowledge_open_source,
            "person_quick_look": self._person_quick_look,
            "navigation_status": self._navigation_status,
            "open_navigation": self._open_navigation,
            "activate_recent": self._activate_recent,
        }

    def handle(self, raw: dict[str, Any]) -> dict[str, Any]:
        if raw.get("client") == CLI_CLIENT:
            try:
                enabled = self.broker._profile_store.preferences()["terminalAccess"]
            except ProfileError as error:
                return self.broker._error(str(error))
            if not enabled:
                return self.broker._error("terminal_access_disabled")
        operation = sanitize_text(raw.get("op"), 40)
        handler = self._handlers.get(operation)
        return handler(raw) if handler else self.broker._error("unsupported_operation")

    def _status(self, raw: dict[str, Any]) -> dict[str, Any]:
        broker = self.broker
        if raw.get("probeMagnus") is True:
            broker._probe_magnus()
        rock = broker._session.status()
        magnus = broker._magnus.status()
        profiles = broker._profile_store.snapshot()
        return broker._ok(
            context=broker._context.value,
            developerMode=broker._developer_mode,
            rock=rock,
            instance=broker._instance_status(),
            magnus=magnus,
            profiles=profiles,
            terminal=broker._terminal_access.status(
                enabled=profiles["preferences"]["terminalAccess"]
            ),
            update=broker._updates.status(
                automatic_install=profiles["preferences"]["automaticUpdates"]
            ),
            capabilities=broker.capabilities(rock, magnus),
            categories=list(broker._mock.categories()),
            magnusBuilds=broker._build_receipts.public_items(),
        )

    def _doctor(self, raw: dict[str, Any]) -> dict[str, Any]:
        broker = self.broker
        refresh = raw.get("refresh") is True
        rock = broker._session.status()
        profiles = broker._profile_store.snapshot()
        terminal = broker._terminal_access.status(
            enabled=profiles["preferences"]["terminalAccess"]
        )
        if refresh:
            broker._probe_magnus(force=True)
        magnus = broker._magnus.status()
        update = broker._updates.status(
            refresh=refresh,
            automatic_install=False,
        )

        checks: list[dict[str, str]] = []

        def check(name: str, state: str, detail: str) -> None:
            checks.append({"name": name, "state": state, "detail": detail})

        check(
            "secure_storage",
            "healthy" if rock.get("available") else "error",
            "Available" if rock.get("available") else "Unavailable",
        )
        check(
            "rock_login",
            "healthy" if rock.get("configured") else "warning",
            "Configured" if rock.get("configured") else "Login required",
        )
        if rock.get("configured"):
            capabilities = self._search_capability_payload(force_refresh=refresh)
            available = capabilities.get("availableCategories", [])
            unavailable = capabilities.get("unavailableCategories", [])
            capability_state = capabilities.get("state")
            check(
                "entity_access",
                "healthy" if capability_state == "ready" else "error",
                (
                    f"{len(available)} available, {len(unavailable)} unavailable"
                    if capability_state == "ready"
                    else "Access check failed"
                ),
            )
        else:
            check("entity_access", "blocked", "Rock login required")
        magnus_state = str(magnus.get("state") or "unknown")
        check(
            "magnus",
            "healthy" if magnus_state == "available" else (
                "error" if magnus_state == "error" else "optional"
            ),
            {
                "available": "Available",
                "error": "Access check failed",
                "signed_out": "Rock login required",
                "unavailable": "Not available for this account",
            }.get(magnus_state, "Not checked"),
        )
        terminal_state = "healthy"
        terminal_detail = "Enabled"
        if not terminal.get("enabled"):
            terminal_state, terminal_detail = "disabled", "Disabled in Settings"
        elif terminal.get("error"):
            terminal_state, terminal_detail = "error", "Launcher unavailable"
        elif not terminal.get("installed"):
            terminal_state, terminal_detail = "warning", "Launcher managed manually"
        check("terminal", terminal_state, terminal_detail)
        update_state = str(update.get("state") or "unknown")
        check(
            "updates",
            "error" if update_state in {"error", "modified"} else "healthy",
            "Managed" if update.get("managed") else "Managed manually",
        )
        overall = (
            "needs_attention"
            if any(item["state"] in {"error", "warning"} for item in checks)
            else "healthy"
        )
        return broker._ok(
            doctor={"state": overall, "redacted": True, "checks": checks}
        )

    def _describe(self, raw: dict[str, Any]) -> dict[str, Any]:
        try:
            description = self.broker._describe_safe_id(
                sanitize_text(raw.get("safeId"), 100)
            )
        except ValueError as error:
            return self.broker._error(str(error))
        return self.broker._ok(description=description)

    def _action_preview(self, raw: dict[str, Any]) -> dict[str, Any]:
        action = sanitize_text(raw.get("action"), 40)
        try:
            description = self.broker._describe_safe_id(
                sanitize_text(raw.get("safeId"), 100)
            )
        except ValueError as error:
            return self.broker._error(str(error))
        allowed = {
            "open": {"open"},
            "knowledgeOpen": {"openSource"},
            "activate": {"open", "build"},
            "download": {"download"},
            "copyHash": {"copyHash"},
            "copyContent": {"copy", "preview"},
            "build": {"build"},
        }
        supported = allowed.get(action, set()).intersection(description["actions"])
        if not supported:
            return self.broker._error("action_not_available")
        side_effects = {
            "open": ["opens_desktop_browser", "adds_recent_link"],
            "knowledgeOpen": ["opens_desktop_browser"],
            "activate": ["opens_browser_or_starts_build"],
            "download": ["creates_private_download"],
            "copyHash": ["changes_clipboard"],
            "copyContent": ["reads_file", "changes_clipboard"],
            "build": ["starts_magnus_deployment", "adds_recent_link"],
        }
        return self.broker._ok(
            dryRun={
                "action": action,
                "target": description,
                "confirmationRequired": True,
                "sideEffects": side_effects[action],
                "executed": False,
            }
        )

    def _ui_handoff_set(self, raw: dict[str, Any]) -> dict[str, Any]:
        try:
            handoff = self.broker._set_ui_handoff(
                raw.get("view"), raw.get("query", "")
            )
        except ValueError as error:
            return self.broker._error(str(error))
        return self.broker._ok(uiHandoffReady=handoff)

    def _ui_handoff_take(self, _raw: dict[str, Any]) -> dict[str, Any]:
        handoff = self.broker._take_ui_handoff()
        return (
            self.broker._ok(uiHandoff=handoff)
            if handoff
            else self.broker._error("ui_handoff_not_found")
        )

    def _set_context(self, raw: dict[str, Any]) -> dict[str, Any]:
        broker = self.broker
        try:
            requested = Context(sanitize_text(raw.get("context"), 8))
        except ValueError:
            return broker._error("invalid_context")
        if requested is Context.DEV and not broker._developer_mode:
            return broker._error("developer_mode_disabled")
        broker._context = requested
        broker._store_context()
        broker._live.clear()
        return broker._ok(
            context=broker._context.value,
            developerMode=broker._developer_mode,
            rock=broker._session.status(),
            instance=broker._instance_status(),
            magnus=broker._magnus.status(),
            profiles=broker._profile_store.snapshot(),
        )

    def _magnus_status(self, _raw: dict[str, Any]) -> dict[str, Any]:
        self.broker._probe_magnus()
        return self.broker._ok(
            magnus=self.broker._magnus.status(),
            magnusBuilds=self.broker._build_receipts.public_items(),
        )

    def _search_capability_payload(
        self, *, force_refresh: bool = False
    ) -> dict[str, Any]:
        broker = self.broker
        if broker._context is Context.DEV:
            return {
                "state": "ready",
                "availableCategories": list(CATEGORIES),
                "unavailableCategories": [],
            }
        if not broker._origin or not broker._session.status()["configured"]:
            return {
                "state": "signed_out",
                "availableCategories": [],
                "unavailableCategories": [],
            }
        try:
            capabilities = broker._live.searchable_categories(force_refresh)
        except RockRestError:
            broker._live_health = HealthState.FAILED
            return {
                "state": "error",
                "availableCategories": [],
                "unavailableCategories": [],
            }
        broker._live_health = HealthState.HEALTHY
        return {
            "state": "ready",
            "availableCategories": list(capabilities.available),
            "unavailableCategories": list(capabilities.unavailable),
        }

    def _search_capabilities(self, raw: dict[str, Any]) -> dict[str, Any]:
        return self.broker._ok(
            searchCapabilities=self._search_capability_payload(
                force_refresh=raw.get("refresh") is True
            )
        )

    def _rock_configure(self, raw: dict[str, Any]) -> dict[str, Any]:
        broker = self.broker
        domain = raw.get("domain")
        username = raw.get("username")
        password = raw.get("password")
        if (
            not isinstance(domain, str)
            or not isinstance(username, str)
            or not isinstance(password, str)
        ):
            return broker._error("invalid_rock_credentials")
        added_profile: RockProfile | None = None
        try:
            origin = validate_rock_origin(domain)
            requested_name = (
                broker._profile_store.validate_name(raw.get("name"), origin)
                if "name" in raw
                else None
            )
            active = broker._profile_store.active()
            if active is None:
                added_profile = broker._profile_store.add(
                    requested_name or default_profile_name(origin), origin
                )
                broker._activate_profile(added_profile)
            elif active.origin != origin:
                return broker._error("profile_domain_mismatch")
            broker._session.configure(username, password)
            if (
                active is not None
                and requested_name is not None
                and requested_name != active.name
            ):
                broker._profile_store.rename(active.profile_id, requested_name)
            broker._reset_magnus_access()
        except OriginError:
            return broker._error("invalid_rock_origin")
        except (RockSessionError, ProfileError) as error:
            if added_profile and not broker._rollback_profile_add(added_profile):
                return broker._error("secure_storage_failed")
            return broker._error(str(error))
        broker._live.clear()
        return broker._ok(
            instance=broker._instance_status(),
            rock=broker._session.status(),
            magnus=broker._magnus.status(),
            refreshLive=True,
            profiles=broker._profile_store.snapshot(),
        )

    def _profiles_status(self, _raw: dict[str, Any]) -> dict[str, Any]:
        return self.broker._profile_response()

    def _profile_add(self, raw: dict[str, Any]) -> dict[str, Any]:
        return self.broker._profile_add(raw)

    def _profile_switch(self, raw: dict[str, Any]) -> dict[str, Any]:
        broker = self.broker
        try:
            profile = broker._profile_store.set_active(raw.get("profileId"))
            broker._activate_profile(profile)
        except (ProfileError, RockSessionError, MagnusError) as error:
            return broker._error(str(error))
        return broker._profile_response(refreshLive=True)

    def _profile_rename(self, raw: dict[str, Any]) -> dict[str, Any]:
        broker = self.broker
        try:
            broker._profile_store.rename(raw.get("profileId"), raw.get("name"))
        except ProfileError as error:
            return broker._error(str(error))
        return broker._profile_response()

    def _profile_credentials_update(self, raw: dict[str, Any]) -> dict[str, Any]:
        broker = self.broker
        username = raw.get("username")
        password = raw.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            return broker._error("invalid_rock_credentials")
        if not broker._profile_store.active():
            return broker._error("profile_not_found")
        try:
            broker._session.configure(username, password)
            broker._reset_magnus_access()
        except RockSessionError as error:
            return broker._error(str(error))
        broker._live.clear()
        return broker._profile_response(refreshLive=True)

    def _profile_test(self, _raw: dict[str, Any]) -> dict[str, Any]:
        broker = self.broker
        if not broker._profile_store.active():
            return broker._error("profile_not_found")
        try:
            broker._session.test_connection()
            broker._reset_magnus_access()
        except RockSessionError as error:
            return broker._error(str(error))
        return broker._profile_response(connection="connected")

    def _profile_sign_out(self, _raw: dict[str, Any]) -> dict[str, Any]:
        broker = self.broker
        if not broker._profile_store.active():
            return broker._error("profile_not_found")
        try:
            broker._session.sign_out()
            broker._reset_magnus_access()
        except RockSessionError as error:
            return broker._error(str(error))
        broker._live.clear()
        return broker._profile_response(connection="signed_out")

    def _profile_remove(self, raw: dict[str, Any]) -> dict[str, Any]:
        return self.broker._profile_remove(raw.get("profileId"))

    def _preferences_update(self, raw: dict[str, Any]) -> dict[str, Any]:
        broker = self.broker
        requested = raw.get("preferences")
        try:
            preferences = broker._profile_store.update_preferences(requested)
        except ProfileError as error:
            return broker._error(str(error))
        if isinstance(requested, dict) and requested.get("terminalAccess") is True:
            broker._terminal_access.ensure_launcher()
        response = broker._profile_response()
        response["update"] = broker._updates.status(
            automatic_install=preferences["automaticUpdates"]
        )
        return response

    def _onboarding_setup_complete(self, raw: dict[str, Any]) -> dict[str, Any]:
        broker = self.broker
        automatic_updates = raw.get("automaticUpdates")
        categories = raw.get("enabledCategories")
        if (
            not isinstance(automatic_updates, bool)
            or not isinstance(categories, list)
        ):
            return broker._error("invalid_onboarding_preferences")
        capabilities = self._search_capability_payload()
        if capabilities["state"] != "ready":
            return broker._error("search_access_not_ready")
        available = set(capabilities["availableCategories"])
        if not set(categories).issubset(available):
            return broker._error("invalid_onboarding_preferences")
        current = broker._profile_store.preferences()["enabledCategories"]
        categories = [
            item
            for item in CATEGORIES
            if item in categories or (item not in available and item in current)
        ]
        try:
            preferences = broker._profile_store.update_preferences(
                {
                    "automaticUpdates": automatic_updates,
                    "automaticUpdatesPrompted": True,
                    "onboardingSetupCompleted": True,
                    "enabledCategories": categories,
                }
            )
        except ProfileError as error:
            return broker._error(
                "invalid_onboarding_preferences"
                if str(error) == "invalid_preferences"
                else str(error)
            )
        response = broker._profile_response()
        response["update"] = broker._updates.status(
            automatic_install=preferences["automaticUpdates"]
        )
        response["onboardingSetup"] = {
            "automaticUpdates": automatic_updates,
            "enabledCategories": preferences["enabledCategories"],
        }
        return response

    def _update_status(self, _raw: dict[str, Any]) -> dict[str, Any]:
        preferences = self.broker._profile_store.preferences()
        return self.broker._ok(
            update=self.broker._updates.status(
                automatic_install=preferences["automaticUpdates"]
            )
        )

    def _update_check(self, _raw: dict[str, Any]) -> dict[str, Any]:
        preferences = self.broker._profile_store.preferences()
        return self.broker._ok(
            update=self.broker._updates.status(
                refresh=True,
                automatic_install=preferences["automaticUpdates"],
            )
        )

    def _update_start(self, _raw: dict[str, Any]) -> dict[str, Any]:
        try:
            update = self.broker._updates.start_update()
        except UpdateError as error:
            return self.broker._error(str(error))
        return self.broker._ok(update=update)

    def _recent_links_clear(self, _raw: dict[str, Any]) -> dict[str, Any]:
        if not self.broker._quick_returns.clear():
            return self.broker._error("recent_links_clear_failed")
        return self.broker._ok(quickReturns=[])

    def _require_prod(self) -> dict[str, Any] | None:
        return (
            None
            if self.broker._context is Context.PROD
            else self.broker._error("magnus_requires_prod")
        )

    def _safe_magnus_id(self, raw: dict[str, Any], default: object = None) -> str | None:
        value = raw.get("safeId", default)
        return sanitize_text(value, 100) if isinstance(value, str) else None

    def _magnus_browse(self, raw: dict[str, Any]) -> dict[str, Any]:
        broker = self.broker
        if error := self._require_prod():
            return error
        safe_id = self._safe_magnus_id(raw, "")
        if safe_id is None:
            return broker._error("invalid_magnus_item")
        try:
            browser = broker._magnus.browse(safe_id)
        except MagnusError as error:
            return broker._error(str(error))
        return broker._ok(
            magnus=broker._magnus.status(),
            magnusBrowser=browser,
            magnusBuilds=broker._build_receipts.public_items(),
        )

    def _magnus_preview(self, raw: dict[str, Any]) -> dict[str, Any]:
        return self._magnus_value(
            raw, "preview", "magnusPreview", include_status=True
        )

    def _magnus_download(self, raw: dict[str, Any]) -> dict[str, Any]:
        return self._magnus_value(raw, "download", "magnusDownload")

    def _magnus_hash(self, raw: dict[str, Any]) -> dict[str, Any]:
        return self._magnus_value(raw, "file_hash", "magnusHash")

    def _magnus_value(
        self,
        raw: dict[str, Any],
        method: str,
        response_key: str,
        include_status: bool = False,
    ) -> dict[str, Any]:
        broker = self.broker
        if error := self._require_prod():
            return error
        safe_id = self._safe_magnus_id(raw)
        if safe_id is None:
            return broker._error("invalid_magnus_item")
        try:
            value = getattr(broker._magnus, method)(safe_id)
        except MagnusError as error:
            return broker._error(str(error))
        payload = {response_key: value}
        if include_status:
            payload["magnus"] = broker._magnus.status()
        return broker._ok(**payload)

    def _magnus_copy(self, raw: dict[str, Any]) -> dict[str, Any]:
        broker = self.broker
        if error := self._require_prod():
            return error
        safe_id = self._safe_magnus_id(raw)
        value = raw.get("value")
        if safe_id is None or value not in {"content", "hash"}:
            return broker._error("invalid_magnus_item")
        try:
            copied_value = broker._magnus.copy_value(safe_id, value)
        except MagnusError as error:
            return broker._error(str(error))
        if not broker._clipboard_writer(copied_value):
            return broker._error("clipboard_unavailable")
        return broker._ok(magnusCopied={"value": value})

    def _magnus_open(self, raw: dict[str, Any]) -> dict[str, Any]:
        broker = self.broker
        if error := self._require_prod():
            return error
        safe_id = self._safe_magnus_id(raw)
        if safe_id is None:
            return broker._error("invalid_magnus_item")
        try:
            target = broker._magnus.view_target(safe_id)
        except MagnusError as error:
            return broker._error(str(error))
        return broker._open_target(target)

    def _magnus_build(self, raw: dict[str, Any]) -> dict[str, Any]:
        broker = self.broker
        if error := self._require_prod():
            return error
        if raw.get("confirmed") is not True:
            return broker._error("build_confirmation_required")
        safe_id = self._safe_magnus_id(raw)
        if safe_id is None:
            return broker._error("invalid_magnus_item")
        try:
            outcome = broker._magnus.build(safe_id)
        except MagnusError as error:
            return broker._error(str(error))
        return broker._complete_build(outcome)

    def _magnus_builds(self, _raw: dict[str, Any]) -> dict[str, Any]:
        return self.broker._ok(
            magnusBuilds=self.broker._build_receipts.public_items()
        )

    def _magnus_build_status(self, raw: dict[str, Any]) -> dict[str, Any]:
        receipt = self.broker._build_receipts.get(raw.get("buildId"))
        return (
            self.broker._ok(magnusBuildStatus=receipt)
            if receipt
            else self.broker._error("build_not_found")
        )

    def _search(self, raw: dict[str, Any]) -> dict[str, Any]:
        broker = self.broker
        query, category = parse_search_query(raw.get("query"))
        if category == KNOWLEDGE_CATEGORY:
            if len(query) < 3:
                return broker._ok(
                    context=broker._context.value,
                    results=[],
                    source="knowledge",
                    unavailable=[],
                )
            try:
                results = broker._knowledge.search(query)
            except RockKbError:
                return broker._ok(
                    context=broker._context.value,
                    results=[],
                    source="knowledge_unavailable",
                    unavailable=[],
                )
            return broker._ok(
                context=broker._context.value,
                results=results,
                source="knowledge",
                unavailable=[],
            )
        preferences = broker._profile_store.preferences()
        enabled_categories = preferences["enabledCategories"]
        unavailable_categories = [category] if category else enabled_categories
        if category and category not in enabled_categories:
            return broker._ok(
                context=broker._context.value,
                results=[],
                source="disabled",
                unavailable=[],
            )
        if broker._context is Context.DEV:
            return broker._ok(
                context=broker._context.value,
                results=[
                    row
                    for row in broker._mock.search(query, category=category)
                    if row["category"] in enabled_categories
                ],
                source="synthetic",
                unavailable=[],
            )
        if not broker._origin or not broker._session.status()["configured"]:
            return broker._ok(
                context=broker._context.value,
                results=[],
                source="unavailable",
                unavailable=unavailable_categories,
                rock=broker._session.status(),
                magnus=broker._magnus.status(),
            )
        capabilities = self._search_capability_payload()
        if capabilities["state"] != "ready":
            return broker._ok(
                context=broker._context.value,
                results=[],
                source="access_check_failed",
                unavailable=[],
                searchCapabilities=capabilities,
                rock=broker._session.status(),
                magnus=broker._magnus.status(),
            )
        available = set(capabilities["availableCategories"])
        effective_categories = [
            item for item in enabled_categories if item in available
        ]
        unavailable_categories = [category] if category else effective_categories
        if category and category not in available:
            return broker._ok(
                context=broker._context.value,
                results=[],
                source="not_authorized",
                unavailable=[],
                searchCapabilities=capabilities,
                rock=broker._session.status(),
                magnus=broker._magnus.status(),
            )
        if not query and category is None:
            return broker._ok(
                context=broker._context.value,
                results=[],
                source="live",
                unavailable=[],
                searchCapabilities=capabilities,
                rock=broker._session.status(),
                magnus=broker._magnus.status(),
            )
        try:
            batch = broker._live.search(
                query,
                category,
                categories=effective_categories,
                include_person_context=preferences["showPersonContext"],
            )
        except RockRestError:
            broker._live_health = HealthState.FAILED
            return broker._ok(
                context=broker._context.value,
                results=[],
                source="unavailable",
                unavailable=unavailable_categories,
                rock=broker._session.status(),
                magnus=broker._magnus.status(),
            )
        results = list(batch.results)
        unavailable = list(batch.unavailable)
        if category is None:
            try:
                results = broker._matching_personal_links(
                    query, broker._live.personal_links()
                ) + results
            except RockRestError:
                unavailable.append("Personal Links")
        broker._live_health = (
            HealthState.STALE if unavailable else HealthState.HEALTHY
        )
        return broker._ok(
            context=broker._context.value,
            results=results,
            source="live",
            unavailable=unavailable,
            rock=broker._session.status(),
            magnus=broker._magnus.status(),
            searchCapabilities=capabilities,
        )

    def _knowledge_result(self, raw: dict[str, Any]) -> dict[str, Any]:
        return self.broker._knowledge_detail(
            sanitize_text(raw.get("safeId"), 100)
        )

    def _knowledge_search(self, raw: dict[str, Any]) -> dict[str, Any]:
        broker = self.broker
        query = sanitize_text(raw.get("query"), 120)
        try:
            results = broker._knowledge.search(query)
        except RockKbError:
            return broker._ok(
                context=broker._context.value,
                knowledgeResults=[],
                knowledgeSource="unavailable",
            )
        return broker._ok(
            context=broker._context.value,
            knowledgeResults=results,
            knowledgeSource="public",
        )

    def _knowledge_open_source(self, raw: dict[str, Any]) -> dict[str, Any]:
        return self.broker._open_knowledge_source(
            sanitize_text(raw.get("safeId"), 100)
        )

    def _person_quick_look(self, raw: dict[str, Any]) -> dict[str, Any]:
        broker = self.broker
        safe_id = sanitize_text(raw.get("safeId"), 100)
        person = (
            broker._mock.person_quick_look(safe_id)
            if broker._context is Context.DEV
            else broker._live.person_quick_look(safe_id)
        )
        return broker._ok(person=person) if person else broker._error("not_found")

    def _navigation_status(self, raw: dict[str, Any]) -> dict[str, Any]:
        section = raw.get("section", "all")
        if not isinstance(section, str) or section not in {
            "all",
            "personal",
            "quick_returns",
        }:
            return self.broker._error("invalid_navigation_section")
        return self.broker._navigation_status(section)

    def _open_navigation(self, raw: dict[str, Any]) -> dict[str, Any]:
        return self.broker._open_navigation(sanitize_text(raw.get("safeId"), 100))

    def _activate_recent(self, raw: dict[str, Any]) -> dict[str, Any]:
        return self.broker._activate_recent(
            sanitize_text(raw.get("safeId"), 100),
            raw.get("confirmed") is True,
        )

import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from rock_lens_broker.broker import Broker
from rock_lens_broker.contracts import (
    ALLOWED_PERSON_KEYS,
    ALLOWED_RESULT_KEYS,
    CATEGORIES,
    DEVELOPER_MODE_ENV,
    KNOWLEDGE_CATEGORY,
    SEARCH_SCOPE_ALIASES,
    developer_mode_enabled,
    parse_search_query,
)
from rock_lens_broker.instance import InstanceStore
from rock_lens_broker.magnus_adapter import MagnusBuildOutcome
from rock_lens_broker.navigation import NavigationTarget
from rock_lens_broker.origin import DEFAULT_ROCK_ORIGIN
from rock_lens_broker.rock_rest_adapter import SearchBatch, SearchCapabilities
from rock_lens_broker.terminal_access import CLI_CLIENT


class FakeSession:
    def __init__(self, configured):
        self.configured = configured
        self.saved = None
        self.server = DEFAULT_ROCK_ORIGIN

    def status(self):
        return {
            "available": True,
            "configured": self.configured,
            "state": "ready" if self.configured else "signed_out",
            "server": self.server.removeprefix("https://"),
        }

    @contextmanager
    def authenticated_cookie(self):
        yield ".ROCK=test-session"

    def invalidate_authenticated_cookie(self):
        return None

    def configure(self, username, password):
        self.saved = (username, password)
        self.configured = True

    def set_server(self, value):
        self.server = value

    def set_profile(self, profile_id, server):
        self.profile_id = profile_id
        self.server = server

    def clear_profile(self):
        self.profile_id = ""
        self.server = ""
        self.configured = False

    def migrate_legacy_credentials(self):
        return False

    def sign_out(self):
        self.saved = None
        self.configured = False

    def remove_profile_credentials(self, profile_id):
        if getattr(self, "profile_id", "") == profile_id:
            self.saved = None
            self.configured = False

    def test_connection(self):
        if not self.configured:
            from rock_lens_broker.rock_session import RockSessionError

            raise RockSessionError("rock_login_required")


class FailedRollbackSession(FakeSession):
    def configure(self, username, password):
        from rock_lens_broker.rock_session import RockSessionError

        raise RockSessionError("rock_login_failed")

    def remove_profile_credentials(self, profile_id):
        from rock_lens_broker.rock_session import RockSessionError

        raise RockSessionError("secure_storage_failed")


class FakeMagnus:
    def __init__(self, available=False):
        self.available = available
        self.server = DEFAULT_ROCK_ORIGIN
        self.state = "available" if available else "unavailable"
        self.probe_calls = 0
        self.build_calls = []

    def status(self):
        return {
            "available": self.available,
            "configured": True,
            "state": self.state,
            "mode": "controlled",
            "capabilities": ["browse", "preview", "hash", "download", "copy", "open", "mobile_app_build"] if self.available else [],
            "server": self.server.removeprefix("https://"),
        }

    def set_server(self, value):
        self.server = value

    def set_profile(self, profile_id, server):
        self.profile_id = profile_id
        self.server = server

    def clear_profile(self):
        self.profile_id = ""
        self.server = ""
        self.available = False
        self.state = "signed_out"

    def reset_access(self):
        self.available = False
        self.state = "unknown"

    def probe(self):
        self.probe_calls += 1
        if self.state == "unknown":
            self.state = "unavailable"
        self.available = self.state == "available"
        return self.available

    def browse(self, safe_id=""):
        return {"folderId": safe_id, "title": "Magnus", "items": []}

    def preview(self, safe_id):
        return {
            "safeId": safe_id,
            "title": "test.lava",
            "content": "test",
            "sha256": "a" * 64,
            "sizeBytes": 4,
            "previewAvailable": True,
            "actions": ["download", "copyHash", "copy", "view"],
        }

    def download(self, safe_id):
        return {
            "title": "test.lava",
            "savedAs": "test.lava",
            "folder": "Downloads",
            "sizeBytes": 4,
            "sha256": "a" * 64,
        }

    def copy_value(self, safe_id, value):
        return "test" if value == "content" else "a" * 64

    def file_hash(self, safe_id):
        return {
            "title": "test.lava",
            "sizeBytes": 4,
            "sha256": "a" * 64,
        }

    def view_target(self, safe_id):
        return NavigationTarget(
            "test.lava", "Magnus File", 80, self.server + "/page/123"
        )

    def build(self, safe_id):
        self.build_calls.append(("descriptor", safe_id))
        return self._build_outcome()

    def build_recent(self, url, title):
        self.build_calls.append(("recent", url, title))
        return self._build_outcome()

    def _build_outcome(self):
        return MagnusBuildOutcome(
            "ONE&ALL Mobile",
            "Build queued.",
            NavigationTarget(
                "Deploy ONE&ALL Mobile",
                "Magnus Build",
                5,
                self.server + "/api/TriumphTech/Magnus/Build/mobileapps/14",
            ),
        )


class FakeLive:
    def __init__(self):
        self.search_calls = []
        self.search_categories = []
        self.personal_link_calls = 0
        self.cleared = False
        self.available_categories = list(CATEGORIES)
        self.capability_calls = []
        self.requested_enabled_categories = []
        self.target = NavigationTarget(
            "Ada Rivera",
            "Person",
            10,
            "https://rock.example.org/Person/17",
        )

    def set_origin(self, origin):
        self.target = NavigationTarget(
            "Ada Rivera", "Person", 10, origin + "/Person/17"
        )

    def clear(self):
        self.cleared = True

    def searchable_categories(self, force_refresh=False):
        self.capability_calls.append(force_refresh)
        unavailable = [
            category
            for category in CATEGORIES
            if category not in self.available_categories
        ]
        return SearchCapabilities(
            tuple(self.available_categories), tuple(unavailable)
        )

    def search(
        self,
        query,
        category=None,
        categories=None,
        include_person_context=True,
    ):
        self.search_calls.append(query)
        self.search_categories.append(category)
        self.requested_enabled_categories.append(categories)
        return SearchBatch(
            [
                {
                    "category": "People",
                    "safeId": "rock-safe-person",
                    "title": "Ada Rivera",
                    "subtitle": "Person · live Rock record",
                    "status": "Live",
                    "canOpen": True,
                }
            ],
            (),
        )

    def person_quick_look(self, safe_id):
        if safe_id != "rock-safe-person":
            return None
        return {
            "safeId": safe_id,
            "displayName": "Ada Rivera",
            "subtitle": "Live Rock record · read-only",
            "campus": "Not requested",
        }

    def personal_links(self, force_refresh=False):
        self.personal_link_calls += 1
        return [
            {
                "safeId": "rock-safe-link",
                "title": "People",
                "section": "My tools",
                "isShared": False,
            }
        ]

    def resolve(self, safe_id):
        return (
            self.target if safe_id in {"rock-safe-person", "rock-safe-link"} else None
        )


class FakeUpdates:
    def __init__(self):
        self.status_calls = []
        self.start_calls = 0

    def status(self, *, refresh=False, automatic_install=False):
        self.status_calls.append((refresh, automatic_install))
        return {
            "managed": True,
            "state": "available" if refresh else "current",
            "currentVersion": "0.15.0",
            "availableVersion": "0.16.0" if refresh else "0.15.0",
            "lastCheckedAt": "2026-09-02T12:30:00Z",
            "lastUpdatedAt": "",
            "updateAvailable": refresh,
            "error": "",
        }

    def start_update(self):
        self.start_calls += 1
        return {
            "managed": True,
            "state": "updating",
            "currentVersion": "0.15.0",
            "availableVersion": "0.16.0",
            "lastCheckedAt": "2026-09-02T12:30:00Z",
            "lastUpdatedAt": "",
            "updateAvailable": True,
            "error": "",
        }


class FakeKnowledge:
    def __init__(self):
        self.search_calls = []
        self.detail_calls = []
        self.source_calls = []

    def search(self, query):
        self.search_calls.append(query)
        return [
            {
                "category": "Knowledge",
                "safeId": "kb-safe-result",
                "title": "Diagnose labels",
                "subtitle": "Check the printer route.",
                "status": "Community reviewed",
                "canOpen": True,
            }
        ]

    def detail(self, safe_id):
        self.detail_calls.append(safe_id)
        if safe_id != "kb-safe-result":
            from rock_lens_broker.rock_kb_adapter import RockKbError

            raise RockKbError("knowledge_result_not_found")
        return {
            "safeId": safe_id,
            "title": "Diagnose labels",
            "kind": "Task card",
            "body": "Check the printer route.",
            "trust": "Community reviewed",
            "claimTier": "Source backed",
            "version": "Version not specified",
            "sourceHost": "community.rockrms.com",
            "canOpenSource": True,
            "attribution": "Rock Agent Knowledge Base · ONE&ALL Church",
        }

    def source_url(self, safe_id):
        self.source_calls.append(safe_id)
        return (
            "https://community.rockrms.com/documentation"
            if safe_id == "kb-safe-result"
            else None
        )


class BrokerContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "context"
        self.instance = Path(self.tmp.name) / "instance.json"
        self.broker = Broker(
            self.state,
            instance_file=self.instance,
            developer_mode=True,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_context_defaults_dev_and_persists_explicitly(self):
        self.assertEqual(self.broker.handle({"op": "status"})["context"], "DEV")
        self.assertEqual(self.state.read_text(encoding="utf-8"), "DEV\n")
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)
        self.assertEqual(
            self.broker.handle({"op": "set_context", "context": "PROD"})["context"],
            "PROD",
        )
        self.assertEqual(
            Broker(
                self.state,
                instance_file=self.instance,
                developer_mode=True,
            ).handle({"op": "status"})["context"],
            "PROD",
        )

    def test_update_operations_are_bounded_and_follow_the_saved_preference(self):
        updates = FakeUpdates()
        broker = Broker(
            self.state,
            instance_file=self.instance,
            developer_mode=True,
            updates=updates,
        )

        status = broker.handle({"op": "update_status"})
        self.assertEqual(status["update"]["state"], "current")
        self.assertEqual(updates.status_calls[-1], (False, False))

        checked = broker.handle({"op": "update_check"})
        self.assertTrue(checked["update"]["updateAvailable"])
        self.assertEqual(updates.status_calls[-1], (True, False))

        preference = broker.handle(
            {
                "op": "preferences_update",
                "preferences": {"automaticUpdates": True},
            }
        )
        self.assertTrue(preference["profiles"]["preferences"]["automaticUpdates"])
        self.assertEqual(updates.status_calls[-1], (False, True))

        started = broker.handle({"op": "update_start"})
        self.assertEqual(started["update"]["state"], "updating")
        self.assertEqual(updates.start_calls, 1)

    def test_official_terminal_client_is_enabled_by_default_and_can_be_disabled(self):
        broker = Broker(
            self.state,
            instance_file=self.instance,
            developer_mode=True,
        )

        self.assertTrue(broker.handle({"op": "status", "client": CLI_CLIENT})["ok"])
        disabled = broker.handle(
            {
                "op": "preferences_update",
                "preferences": {"terminalAccess": False},
            }
        )
        self.assertFalse(disabled["profiles"]["preferences"]["terminalAccess"])
        self.assertEqual(
            broker.handle({"op": "status", "client": CLI_CLIENT}),
            {"ok": False, "error": "terminal_access_disabled"},
        )
        self.assertTrue(broker.handle({"op": "status"})["ok"])

    def test_onboarding_setup_choices_are_explicit_and_persisted(self):
        updates = FakeUpdates()
        broker = Broker(
            self.state,
            instance_file=self.instance,
            developer_mode=True,
            updates=updates,
        )

        declined = broker.handle(
            {
                "op": "onboarding_setup_complete",
                "automaticUpdates": False,
                "enabledCategories": ["People", "Group Types"],
            }
        )
        self.assertFalse(declined["onboardingSetup"]["automaticUpdates"])
        self.assertEqual(
            declined["onboardingSetup"]["enabledCategories"],
            ["People", "Group Types"],
        )
        self.assertFalse(
            declined["profiles"]["preferences"]["automaticUpdates"]
        )
        self.assertTrue(
            declined["profiles"]["preferences"]["automaticUpdatesPrompted"]
        )
        self.assertTrue(
            declined["profiles"]["preferences"]["onboardingSetupCompleted"]
        )
        self.assertEqual(updates.status_calls[-1], (False, False))

        enabled = broker.handle(
            {
                "op": "onboarding_setup_complete",
                "automaticUpdates": True,
                "enabledCategories": list(CATEGORIES),
            }
        )
        self.assertTrue(enabled["onboardingSetup"]["automaticUpdates"])
        self.assertTrue(enabled["profiles"]["preferences"]["automaticUpdates"])
        self.assertTrue(
            enabled["profiles"]["preferences"]["automaticUpdatesPrompted"]
        )
        self.assertEqual(updates.status_calls[-1], (False, True))

        self.assertEqual(
            broker.handle(
                {
                    "op": "onboarding_setup_complete",
                    "automaticUpdates": "yes",
                    "enabledCategories": [],
                }
            ),
            {"ok": False, "error": "invalid_onboarding_preferences"},
        )
        self.assertEqual(
            broker.handle(
                {
                    "op": "onboarding_setup_complete",
                    "automaticUpdates": False,
                    "enabledCategories": ["Unknown"],
                }
            ),
            {"ok": False, "error": "invalid_onboarding_preferences"},
        )

    def test_normal_mode_forces_prod_and_rejects_dev_context(self):
        self.state.write_text("DEV\n", encoding="utf-8")
        broker = Broker(
            self.state,
            instance_file=self.instance,
            developer_mode=False,
        )
        status = broker.handle({"op": "status"})
        self.assertEqual(status["context"], "PROD")
        self.assertFalse(status["developerMode"])
        mock = next(
            item for item in status["capabilities"] if item["name"] == "mock"
        )
        self.assertEqual(mock["state"], "unknown")
        self.assertEqual(mock["detail"], "Developer mode disabled")
        self.assertEqual(self.state.read_text(encoding="utf-8"), "PROD\n")
        self.assertEqual(
            broker.handle({"op": "set_context", "context": "DEV"}),
            {"ok": False, "error": "developer_mode_disabled"},
        )
        response = broker.handle({"op": "search", "query": "Ada"})
        self.assertEqual(response["source"], "unavailable")
        self.assertEqual(response["results"], [])

    def test_developer_mode_environment_flag_requires_exact_one(self):
        with patch.dict(os.environ, {DEVELOPER_MODE_ENV: "1"}):
            self.assertTrue(developer_mode_enabled())
            status = Broker(self.state, instance_file=self.instance).handle(
                {"op": "status"}
            )
            self.assertTrue(status["developerMode"])
            self.assertEqual(status["context"], "DEV")
        for value in ("true", "yes", "0", ""):
            with self.subTest(value=value), patch.dict(
                os.environ, {DEVELOPER_MODE_ENV: value}
            ):
                self.assertFalse(developer_mode_enabled())

    def test_invalid_context_fails_closed(self):
        self.assertEqual(
            self.broker.handle({"op": "set_context", "context": "staging"}),
            {"ok": False, "error": "invalid_context"},
        )

    def test_all_categories_and_allowlisted_search_contract(self):
        response = self.broker.handle({"op": "search", "query": ""})
        self.assertEqual(
            {row["category"] for row in response["results"]}, set(CATEGORIES)
        )
        for row in response["results"]:
            self.assertLessEqual(set(row), ALLOWED_RESULT_KEYS)

    def test_entity_prefixes_scope_dev_search_and_preserve_unknown_prefixes(self):
        for prefix, category in SEARCH_SCOPE_ALIASES.items():
            with self.subTest(prefix=prefix):
                response = self.broker.handle({"op": "search", "query": f"{prefix}:"})
                self.assertEqual(
                    {row["category"] for row in response["results"]}, {category}
                )

        self.assertEqual(parse_search_query("g: youth"), ("youth", "Groups"))
        self.assertEqual(
            parse_search_query("kb: label printing"),
            ("label printing", KNOWLEDGE_CATEGORY),
        )
        self.assertEqual(
            parse_search_query("knowledge: Lava fields"),
            ("Lava fields", KNOWLEDGE_CATEGORY),
        )
        self.assertEqual(parse_search_query("unknown: youth"), ("unknown: youth", None))

    def test_knowledge_scope_is_explicit_credentialless_and_opens_only_opaque_sources(self):
        live = FakeLive()
        knowledge = FakeKnowledge()
        opened = []
        broker = Broker(
            self.state,
            session=FakeSession(False),
            magnus=FakeMagnus(False),
            live=live,
            knowledge=knowledge,
            url_opener=lambda url: opened.append(url) is None,
            instance_file=self.instance,
        )

        too_short = broker.handle({"op": "search", "query": "kb: ab"})
        response = broker.handle(
            {"op": "search", "query": "kb: labels not printing"}
        )
        dedicated = broker.handle(
            {"op": "knowledge_search", "query": "mm: group member"}
        )

        self.assertEqual(too_short["results"], [])
        self.assertEqual(response["source"], "knowledge")
        self.assertEqual(response["results"][0]["safeId"], "kb-safe-result")
        self.assertEqual(dedicated["knowledgeSource"], "public")
        self.assertEqual(dedicated["knowledgeResults"][0]["safeId"], "kb-safe-result")
        self.assertEqual(
            knowledge.search_calls, ["labels not printing", "mm: group member"]
        )
        self.assertEqual(live.search_calls, [])

        detail = broker.handle(
            {"op": "knowledge_result", "safeId": "kb-safe-result"}
        )
        self.assertEqual(detail["knowledgeDetail"]["kind"], "Task card")
        opened_response = broker.handle(
            {"op": "knowledge_open_source", "safeId": "kb-safe-result"}
        )
        self.assertTrue(opened_response["knowledgeOpened"])
        self.assertEqual(
            opened, ["https://community.rockrms.com/documentation"]
        )
        self.assertEqual(
            broker.handle(
                {
                    "op": "knowledge_open_source",
                    "safeId": "https://attacker.example/",
                }
            ),
            {"ok": False, "error": "knowledge_source_not_found"},
        )

    def test_person_quick_look_is_privacy_minimal(self):
        person = self.broker.handle(
            {"op": "person_quick_look", "safeId": "mock-person-ada"}
        )["person"]
        self.assertLessEqual(set(person), ALLOWED_PERSON_KEYS)
        serialized = json.dumps(person).lower()
        for forbidden in ("email", "phone", "address", "birth", "cookie", "token"):
            self.assertNotIn(forbidden, serialized)

    def test_no_mutation_or_job_run_operation(self):
        for op in ("run_job", "run_now", "insert", "update", "delete"):
            self.assertEqual(
                self.broker.handle({"op": op})["error"], "unsupported_operation"
            )

    def test_live_capabilities_are_not_healthy(self):
        states = {
            row["name"]: row["state"]
            for row in self.broker.handle({"op": "status"})["capabilities"]
        }
        self.assertEqual(states["mock"], "healthy")
        self.assertTrue(
            all(
                states[name] != "healthy"
                for name in ("rock_session", "rock_rest", "sql", "magnus")
            )
        )

    def test_status_exposes_only_native_rock_session_authentication(self):
        status = self.broker.handle({"op": "status"})
        self.assertNotIn("auth", status)
        self.assertNotIn(
            "rock_oauth", {capability["name"] for capability in status["capabilities"]}
        )
        for operation in ("auth_status", "auth_login", "auth_disconnect"):
            with self.subTest(operation=operation):
                self.assertEqual(
                    self.broker.handle({"op": operation}),
                    {"ok": False, "error": "unsupported_operation"},
                )

    def test_magnus_contract_is_controlled_and_private(self):
        response = self.broker.handle({"op": "magnus_status"})
        self.assertEqual(response["magnus"]["mode"], "controlled")
        self.assertEqual(
            self.broker.handle({"op": "status"})["magnus"]["mode"],
            "controlled",
        )
        serialized = json.dumps(response).lower()
        for forbidden in ("username", "password", "cookie", "credential"):
            self.assertNotIn(forbidden, serialized)
        for op in (
            "magnus_write",
            "magnus_rm",
            "magnus_mkdir",
            "magnus_touch",
            "magnus_upload",
        ):
            self.assertEqual(
                self.broker.handle({"op": op})["error"], "unsupported_operation"
            )

    def test_prod_search_uses_live_adapter_and_never_synthetic_fallback(self):
        InstanceStore(self.instance).set(DEFAULT_ROCK_ORIGIN)
        live = FakeLive()
        broker = Broker(
            self.state,
            session=FakeSession(True),
            magnus=FakeMagnus(True),
            live=live,
            instance_file=self.instance,
        )
        broker.handle({"op": "set_context", "context": "PROD"})
        response = broker.handle({"op": "search", "query": "Ada"})
        self.assertEqual(response["source"], "live")
        self.assertEqual(live.search_calls, ["Ada"])
        self.assertEqual(live.search_categories, [None])
        self.assertEqual(response["results"][0]["safeId"], "rock-safe-person")

        broker.handle({"op": "search", "query": "g: Delta"})
        self.assertEqual(live.search_calls[-1], "Delta")
        self.assertEqual(live.search_categories[-1], "Groups")

    def test_prod_search_detects_and_enforces_account_entity_access(self):
        InstanceStore(self.instance).set(DEFAULT_ROCK_ORIGIN)
        live = FakeLive()
        live.available_categories = ["People", "Groups", "Pages"]
        broker = Broker(
            self.state,
            session=FakeSession(True),
            magnus=FakeMagnus(False),
            live=live,
            instance_file=self.instance,
        )
        broker.handle({"op": "set_context", "context": "PROD"})

        detected = broker.handle({"op": "search_capabilities"})
        self.assertEqual(detected["searchCapabilities"]["state"], "ready")
        self.assertEqual(
            detected["searchCapabilities"]["availableCategories"],
            ["People", "Groups", "Pages"],
        )
        self.assertIn(
            "Jobs", detected["searchCapabilities"]["unavailableCategories"]
        )

        denied = broker.handle({"op": "search", "query": "j: nightly"})
        self.assertEqual(denied["source"], "not_authorized")
        self.assertEqual(denied["results"], [])
        self.assertEqual(live.search_calls, [])

        allowed = broker.handle({"op": "search", "query": "Ada"})
        self.assertEqual(allowed["source"], "live")
        self.assertEqual(
            live.requested_enabled_categories[-1], ["People", "Groups", "Pages"]
        )

    def test_unscoped_search_includes_matching_personal_links_first(self):
        InstanceStore(self.instance).set(DEFAULT_ROCK_ORIGIN)
        live = FakeLive()
        broker = Broker(
            self.state,
            session=FakeSession(True),
            magnus=FakeMagnus(False),
            live=live,
            instance_file=self.instance,
        )
        broker.handle({"op": "set_context", "context": "PROD"})

        response = broker.handle({"op": "search", "query": "people"})

        self.assertEqual(response["results"][0]["category"], "Personal Links")
        self.assertEqual(response["results"][0]["safeId"], "rock-safe-link")
        self.assertEqual(response["results"][0]["subtitle"], "My tools")
        self.assertEqual(response["results"][0]["status"], "Personal")
        self.assertNotIn("url", json.dumps(response["results"][0]).lower())

        scoped = broker.handle({"op": "search", "query": "p: people"})
        self.assertTrue(
            all(item["category"] != "Personal Links" for item in scoped["results"])
        )

    def test_prod_search_and_links_do_not_require_magnus_access(self):
        InstanceStore(self.instance).set(DEFAULT_ROCK_ORIGIN)
        live = FakeLive()
        broker = Broker(
            self.state,
            session=FakeSession(True),
            magnus=FakeMagnus(False),
            live=live,
            instance_file=self.instance,
        )
        broker.handle({"op": "set_context", "context": "PROD"})

        status = broker.handle({"op": "status"})
        self.assertTrue(status["rock"]["configured"])
        self.assertFalse(status["magnus"]["available"])

        search = broker.handle({"op": "search", "query": "Ada"})
        self.assertEqual(search["source"], "live")
        self.assertEqual(search["results"][0]["safeId"], "rock-safe-person")

        links = broker.handle({"op": "navigation_status", "section": "personal"})
        self.assertTrue(links["personalLinksAvailable"])
        self.assertEqual(links["personalLinks"][0]["safeId"], "rock-safe-link")

    def test_core_status_does_not_wait_for_optional_magnus_probe(self):
        InstanceStore(self.instance).set(DEFAULT_ROCK_ORIGIN)
        magnus = FakeMagnus(False)
        magnus.state = "unknown"
        broker = Broker(
            self.state,
            session=FakeSession(True),
            magnus=magnus,
            live=FakeLive(),
            instance_file=self.instance,
        )

        status = broker.handle({"op": "status"})
        self.assertTrue(status["rock"]["configured"])
        self.assertEqual(magnus.probe_calls, 0)

        broker.handle({"op": "status", "probeMagnus": True})
        self.assertEqual(magnus.probe_calls, 1)

        magnus.state = "unknown"
        broker.handle({"op": "magnus_status"})
        self.assertEqual(magnus.probe_calls, 2)

    def test_magnus_browse_and_preview_use_bounded_operations(self):
        InstanceStore(self.instance).set(DEFAULT_ROCK_ORIGIN)
        broker = Broker(
            self.state,
            session=FakeSession(True),
            magnus=FakeMagnus(True),
            live=FakeLive(),
            instance_file=self.instance,
        )
        broker.handle({"op": "set_context", "context": "PROD"})

        browser = broker.handle({"op": "magnus_browse", "safeId": ""})
        self.assertTrue(browser["ok"])
        self.assertEqual(browser["magnusBrowser"]["items"], [])

        preview = broker.handle(
            {"op": "magnus_preview", "safeId": "opaque-magnus-item"}
        )
        file_hash = broker.handle({"op": "magnus_hash", "safeId": "opaque-magnus-item"})
        self.assertTrue(preview["ok"])
        self.assertEqual(preview["magnus"]["state"], "available")
        self.assertEqual(preview["magnusPreview"]["sha256"], "a" * 64)
        self.assertTrue(file_hash["ok"])
        self.assertEqual(file_hash["magnusHash"]["sha256"], "a" * 64)

    def test_magnus_file_actions_keep_values_private(self):
        InstanceStore(self.instance).set(DEFAULT_ROCK_ORIGIN)
        opened = []
        clipboard = []
        broker = Broker(
            self.state,
            session=FakeSession(True),
            magnus=FakeMagnus(True),
            live=FakeLive(),
            url_opener=lambda url: opened.append(url) is None,
            clipboard_writer=lambda value: clipboard.append(value) is None,
            instance_file=self.instance,
        )
        broker.handle({"op": "set_context", "context": "PROD"})

        downloaded = broker.handle(
            {"op": "magnus_download", "safeId": "opaque-magnus-item"}
        )
        copied = broker.handle(
            {
                "op": "magnus_copy",
                "safeId": "opaque-magnus-item",
                "value": "content",
            }
        )
        opened_response = broker.handle(
            {"op": "magnus_open", "safeId": "opaque-magnus-item"}
        )

        self.assertEqual(downloaded["magnusDownload"]["folder"], "Downloads")
        self.assertEqual(copied["magnusCopied"], {"value": "content"})
        self.assertEqual(clipboard, ["test"])
        self.assertTrue(opened_response["opened"])
        self.assertEqual(opened, [DEFAULT_ROCK_ORIGIN + "/page/123"])
        self.assertNotIn('"content": "test"', json.dumps(copied))

    def test_successful_build_becomes_confirmed_repeatable_recent_link(self):
        InstanceStore(self.instance).set(DEFAULT_ROCK_ORIGIN)
        magnus = FakeMagnus(True)
        broker = Broker(
            self.state,
            session=FakeSession(True),
            magnus=magnus,
            live=FakeLive(),
            instance_file=self.instance,
        )
        broker.handle({"op": "set_context", "context": "PROD"})

        confirmation = broker.handle(
            {"op": "magnus_build", "safeId": "opaque-mobile-app"}
        )
        self.assertEqual(confirmation["error"], "build_confirmation_required")
        self.assertEqual(magnus.build_calls, [])
        built = broker.handle(
            {
                "op": "magnus_build",
                "safeId": "opaque-mobile-app",
                "confirmed": True,
            }
        )

        self.assertEqual(built["magnusBuild"]["message"], "Build queued.")
        self.assertEqual(built["quickReturns"][0]["kind"], "Magnus Build")
        self.assertRegex(
            built["quickReturns"][0]["lastUsedAt"], r"^\d{4}-\d{2}-\d{2}T"
        )
        self.assertNotIn("Build/mobileapps/14", json.dumps(built))
        recent_id = built["quickReturns"][0]["safeId"]
        self.assertEqual(
            broker.handle({"op": "open_navigation", "safeId": recent_id})[
                "error"
            ],
            "build_confirmation_required",
        )
        self.assertEqual(len(magnus.build_calls), 1)

        repeat_confirmation = broker.handle(
            {"op": "activate_recent", "safeId": recent_id}
        )
        self.assertEqual(
            repeat_confirmation["error"], "build_confirmation_required"
        )
        self.assertEqual(len(magnus.build_calls), 1)
        repeated = broker.handle(
            {"op": "activate_recent", "safeId": recent_id, "confirmed": True}
        )

        self.assertTrue(repeated["ok"])
        self.assertEqual(len(magnus.build_calls), 2)
        self.assertEqual(magnus.build_calls[-1][0], "recent")
        self.assertEqual(repeated["quickReturns"][0]["kind"], "Magnus Build")

    def test_prod_without_rock_login_fails_closed_without_live_call(self):
        InstanceStore(self.instance).set(DEFAULT_ROCK_ORIGIN)
        live = FakeLive()
        broker = Broker(
            self.state,
            session=FakeSession(False),
            magnus=FakeMagnus(False),
            live=live,
            instance_file=self.instance,
        )
        broker.handle({"op": "set_context", "context": "PROD"})
        response = broker.handle({"op": "search", "query": "Ada"})
        self.assertEqual(response["source"], "unavailable")
        self.assertEqual(response["results"], [])
        self.assertEqual(live.search_calls, [])

    def test_plugin_can_configure_rock_without_echoing_credentials(self):
        session = FakeSession(False)
        magnus = FakeMagnus(False)
        live = FakeLive()
        broker = Broker(
            self.state,
            session=session,
            magnus=magnus,
            live=live,
            instance_file=self.instance,
        )
        response = broker.handle(
            {
                "op": "rock_configure",
                "name": "Rock Solid Church Production",
                "domain": "rock.example.org",
                "username": "rock-user",
                "password": "private-password",
            }
        )
        self.assertTrue(response["ok"])
        self.assertTrue(response["refreshLive"])
        self.assertEqual(session.saved, ("rock-user", "private-password"))
        self.assertEqual(
            response["profiles"]["profiles"][0]["name"],
            "Rock Solid Church Production",
        )
        self.assertEqual(magnus.server, DEFAULT_ROCK_ORIGIN)
        self.assertEqual(magnus.probe_calls, 0)
        self.assertEqual(InstanceStore(self.instance).get(), DEFAULT_ROCK_ORIGIN)
        serialized = json.dumps(response)
        self.assertNotIn("rock-user", serialized)
        self.assertNotIn("private-password", serialized)

    def test_signed_out_onboarding_updates_the_existing_profile_name(self):
        session = FakeSession(False)
        broker = Broker(
            self.state,
            session=session,
            magnus=FakeMagnus(False),
            live=FakeLive(),
            instance_file=self.instance,
        )
        added = broker.handle(
            {
                "op": "profile_add",
                "name": "Production",
                "domain": "rock.example.org",
                "username": "rock-user",
                "password": "private-password",
            }
        )
        profile_id = added["profiles"]["activeProfileId"]
        broker.handle({"op": "profile_sign_out"})

        configured = broker.handle(
            {
                "op": "rock_configure",
                "name": "Rock Solid Church Production",
                "domain": "rock.example.org",
                "username": "rock-user",
                "password": "private-password",
            }
        )

        self.assertTrue(configured["ok"])
        self.assertEqual(configured["profiles"]["activeProfileId"], profile_id)
        self.assertEqual(
            configured["profiles"]["profiles"][0]["name"],
            "Rock Solid Church Production",
        )

    def test_failed_profile_rollback_returns_stable_error_and_keeps_profile(self):
        broker = Broker(
            self.state,
            session=FailedRollbackSession(False),
            magnus=FakeMagnus(False),
            live=FakeLive(),
            instance_file=self.instance,
        )

        response = broker.handle(
            {
                "op": "profile_add",
                "name": "Retry cleanup",
                "domain": "rock.example.org",
                "username": "rock-user",
                "password": "private-password",
            }
        )

        self.assertEqual(response, {"ok": False, "error": "secure_storage_failed"})
        profiles = broker.handle({"op": "profiles_status"})["profiles"]
        self.assertEqual(len(profiles["profiles"]), 1)

    def test_profile_lifecycle_and_preferences_are_broker_managed(self):
        session = FakeSession(False)
        magnus = FakeMagnus(False)
        live = FakeLive()
        broker = Broker(
            self.state,
            session=session,
            magnus=magnus,
            live=live,
            instance_file=self.instance,
        )
        added = broker.handle(
            {
                "op": "profile_add",
                "name": "Main Campus",
                "domain": "rock.example.org",
                "username": "rock-user",
                "password": "private-password",
            }
        )
        self.assertTrue(added["ok"])
        profile_id = added["profiles"]["activeProfileId"]
        self.assertEqual(added["profiles"]["profiles"][0]["name"], "Main Campus")
        self.assertNotIn("rock-user", json.dumps(added))
        self.assertNotIn("private-password", json.dumps(added))

        preferences = broker.handle(
            {
                "op": "preferences_update",
                "preferences": {
                    "showPersonContext": False,
                    "showMenuBar": False,
                    "enabledCategories": ["Groups"],
                },
            }
        )
        self.assertEqual(
            preferences["profiles"]["preferences"]["enabledCategories"],
            ["Groups"],
        )
        self.assertFalse(preferences["profiles"]["preferences"]["showMenuBar"])
        broker.handle({"op": "set_context", "context": "PROD"})
        search = broker.handle({"op": "search", "query": "Ada"})
        self.assertTrue(search["ok"])
        self.assertEqual(live.search_categories[-1], None)

        signed_out = broker.handle({"op": "profile_sign_out"})
        self.assertEqual(signed_out["connection"], "signed_out")
        self.assertFalse(signed_out["rock"]["configured"])
        removed = broker.handle({"op": "profile_remove", "profileId": profile_id})
        self.assertEqual(removed["profiles"]["profiles"], [])
        self.assertFalse(removed["instance"]["configured"])

    def test_profiles_with_same_domain_have_distinct_ids_and_switch(self):
        session = FakeSession(False)
        magnus = FakeMagnus(False)
        broker = Broker(
            self.state,
            session=session,
            magnus=magnus,
            live=FakeLive(),
            instance_file=self.instance,
        )
        first = broker.handle(
            {
                "op": "profile_add",
                "name": "Staff",
                "domain": DEFAULT_ROCK_ORIGIN,
                "username": "staff",
                "password": "first-password",
            }
        )
        first_id = first["profiles"]["activeProfileId"]
        second = broker.handle(
            {
                "op": "profile_add",
                "name": "Volunteer",
                "domain": DEFAULT_ROCK_ORIGIN,
                "username": "volunteer",
                "password": "second-password",
            }
        )
        second_id = second["profiles"]["activeProfileId"]
        self.assertNotEqual(first_id, second_id)
        switched = broker.handle({"op": "profile_switch", "profileId": first_id})
        self.assertEqual(switched["profiles"]["activeProfileId"], first_id)

    def test_personal_links_and_quick_returns_open_only_by_safe_id(self):
        InstanceStore(self.instance).set(DEFAULT_ROCK_ORIGIN)
        opened = []
        live = FakeLive()
        broker = Broker(
            self.state,
            session=FakeSession(True),
            magnus=FakeMagnus(True),
            live=live,
            url_opener=lambda url: opened.append(url) is None,
            instance_file=self.instance,
            developer_mode=True,
        )
        broker.handle({"op": "set_context", "context": "PROD"})
        recent = broker.handle(
            {"op": "navigation_status", "section": "quick_returns"}
        )
        self.assertEqual(recent, {"ok": True, "quickReturns": []})
        self.assertEqual(live.personal_link_calls, 0)

        personal = broker.handle({"op": "navigation_status", "section": "personal"})
        self.assertNotIn("quickReturns", personal)
        self.assertTrue(personal["personalLinksAvailable"])
        self.assertEqual(live.personal_link_calls, 1)

        navigation = broker.handle({"op": "navigation_status"})
        self.assertTrue(navigation["personalLinksAvailable"])
        self.assertEqual(navigation["personalLinks"][0]["safeId"], "rock-safe-link")
        self.assertEqual(live.personal_link_calls, 2)
        self.assertEqual(
            broker.handle({"op": "navigation_status", "section": "other"}),
            {"ok": False, "error": "invalid_navigation_section"},
        )
        self.assertEqual(
            broker.handle({"op": "navigation_status", "section": []}),
            {"ok": False, "error": "invalid_navigation_section"},
        )
        self.assertEqual(
            broker.handle(
                {
                    "op": "open_navigation",
                    "safeId": "https://attacker.example/",
                }
            )["error"],
            "not_found",
        )
        response = broker.handle({"op": "open_navigation", "safeId": "rock-safe-link"})
        self.assertTrue(response["opened"])
        self.assertEqual(opened, ["https://rock.example.org/Person/17"])
        self.assertEqual(len(response["quickReturns"]), 1)
        quick_id = response["quickReturns"][0]["safeId"]
        self.assertTrue(
            broker.handle({"op": "open_navigation", "safeId": quick_id})["opened"]
        )
        cleared = broker.handle({"op": "recent_links_clear"})
        self.assertEqual(cleared, {"ok": True, "quickReturns": []})
        self.assertEqual(
            broker.handle(
                {"op": "navigation_status", "section": "quick_returns"}
            ),
            {"ok": True, "quickReturns": []},
        )
        broker.handle({"op": "set_context", "context": "DEV"})
        dev_navigation = broker.handle({"op": "navigation_status"})
        self.assertEqual(dev_navigation["personalLinks"], [])
        self.assertEqual(dev_navigation["quickReturns"], [])
        self.assertEqual(
            broker.handle({"op": "open_navigation", "safeId": quick_id})["error"],
            "navigation_requires_prod",
        )

    def test_recent_links_clear_does_not_claim_success_after_unlink_failure(self):
        broker = Broker(
            self.state,
            session=FakeSession(True),
            magnus=FakeMagnus(False),
            live=FakeLive(),
            instance_file=self.instance,
        )
        with patch.object(broker._quick_returns, "clear", return_value=False):
            response = broker.handle({"op": "recent_links_clear"})

        self.assertEqual(
            response, {"ok": False, "error": "recent_links_clear_failed"}
        )


if __name__ == "__main__":
    unittest.main()

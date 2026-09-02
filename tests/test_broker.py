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
    SEARCH_SCOPE_ALIASES,
    developer_mode_enabled,
    parse_search_query,
)
from rock_lens_broker.instance import InstanceStore
from rock_lens_broker.magnus_adapter import MagnusBuildOutcome
from rock_lens_broker.navigation import NavigationTarget
from rock_lens_broker.origin import DEFAULT_ROCK_ORIGIN
from rock_lens_broker.rock_rest_adapter import SearchBatch


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

    def search(
        self,
        query,
        category=None,
        categories=None,
        include_person_context=True,
    ):
        self.search_calls.append(query)
        self.search_categories.append(category)
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

    def personal_links(self):
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


class BrokerContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "context"
        self.config = Path(self.tmp.name) / "oidc.json"
        self.instance = Path(self.tmp.name) / "instance.json"
        self.broker = Broker(
            self.state,
            config_file=self.config,
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
                config_file=self.config,
                developer_mode=True,
            ).handle({"op": "status"})["context"],
            "PROD",
        )

    def test_normal_mode_forces_prod_and_rejects_dev_context(self):
        self.state.write_text("DEV\n", encoding="utf-8")
        broker = Broker(
            self.state,
            config_file=self.config,
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
            status = Broker(self.state, config_file=self.config).handle(
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
        self.assertEqual(parse_search_query("unknown: youth"), ("unknown: youth", None))

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
                for name in ("rock_oauth", "rock_rest", "sql", "magnus")
            )
        )

    def test_auth_contract_is_unconfigured_without_private_details(self):
        response = self.broker.handle({"op": "auth_status"})
        self.assertEqual(
            response["auth"],
            {
                "state": "unconfigured",
                "configured": False,
                "label": "OAuth setup needed",
            },
        )
        serialized = json.dumps(response).lower()
        for forbidden in (
            "issuer",
            "client_id",
            "access_token",
            "refresh_token",
            "client_secret",
        ):
            self.assertNotIn(forbidden, serialized)

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
            config_file=self.config,
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

    def test_prod_search_and_links_do_not_require_magnus_access(self):
        InstanceStore(self.instance).set(DEFAULT_ROCK_ORIGIN)
        live = FakeLive()
        broker = Broker(
            self.state,
            config_file=self.config,
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
            config_file=self.config,
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
            config_file=self.config,
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
        self.assertTrue(preview["ok"])
        self.assertEqual(preview["magnusPreview"]["sha256"], "a" * 64)

    def test_magnus_file_actions_keep_values_private(self):
        InstanceStore(self.instance).set(DEFAULT_ROCK_ORIGIN)
        opened = []
        clipboard = []
        broker = Broker(
            self.state,
            config_file=self.config,
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
            config_file=self.config,
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
            config_file=self.config,
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
            config_file=self.config,
            session=session,
            magnus=magnus,
            live=live,
        )
        response = broker.handle(
            {
                "op": "rock_configure",
                "domain": "rock.example.org",
                "username": "rock-user",
                "password": "private-password",
            }
        )
        self.assertTrue(response["ok"])
        self.assertTrue(response["refreshLive"])
        self.assertEqual(session.saved, ("rock-user", "private-password"))
        self.assertEqual(magnus.server, DEFAULT_ROCK_ORIGIN)
        self.assertEqual(magnus.probe_calls, 0)
        self.assertEqual(InstanceStore(self.instance).get(), DEFAULT_ROCK_ORIGIN)
        serialized = json.dumps(response)
        self.assertNotIn("rock-user", serialized)
        self.assertNotIn("private-password", serialized)

    def test_profile_lifecycle_and_preferences_are_broker_managed(self):
        session = FakeSession(False)
        magnus = FakeMagnus(False)
        live = FakeLive()
        broker = Broker(
            self.state,
            config_file=self.config,
            session=session,
            magnus=magnus,
            live=live,
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
                    "enabledCategories": ["Groups"],
                },
            }
        )
        self.assertEqual(
            preferences["profiles"]["preferences"]["enabledCategories"],
            ["Groups"],
        )
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
            config_file=self.config,
            session=session,
            magnus=magnus,
            live=FakeLive(),
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
            config_file=self.config,
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


if __name__ == "__main__":
    unittest.main()

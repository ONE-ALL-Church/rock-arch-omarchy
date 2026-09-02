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
from rock_lens_broker.navigation import NavigationTarget
from rock_lens_broker.origin import DEFAULT_ROCK_ORIGIN
from rock_lens_broker.rock_rest_adapter import SearchBatch


class FakeMagnus:
    def __init__(self, configured):
        self.configured = configured
        self.saved = None
        self.server = DEFAULT_ROCK_ORIGIN

    def status(self):
        return {
            "available": True,
            "configured": self.configured,
            "mode": "read_only",
            "server": self.server.removeprefix("https://"),
        }

    @contextmanager
    def authenticated_cookie(self):
        yield ".ROCK=test-session"

    def configure(self, username, password):
        self.saved = (username, password)
        self.configured = True

    def set_server(self, value):
        self.server = value


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

    def search(self, query, category=None):
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

    def test_magnus_contract_is_read_only_and_private(self):
        response = self.broker.handle({"op": "magnus_status"})
        self.assertEqual(response["magnus"]["mode"], "read_only")
        self.assertEqual(
            self.broker.handle({"op": "status"})["magnus"]["mode"],
            "read_only",
        )
        serialized = json.dumps(response).lower()
        for forbidden in ("username", "password", "cookie", "credential"):
            self.assertNotIn(forbidden, serialized)
        for op in (
            "magnus_write",
            "magnus_build",
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

    def test_prod_without_magnus_fails_closed_without_live_call(self):
        InstanceStore(self.instance).set(DEFAULT_ROCK_ORIGIN)
        live = FakeLive()
        broker = Broker(
            self.state,
            config_file=self.config,
            magnus=FakeMagnus(False),
            live=live,
            instance_file=self.instance,
        )
        broker.handle({"op": "set_context", "context": "PROD"})
        response = broker.handle({"op": "search", "query": "Ada"})
        self.assertEqual(response["source"], "unavailable")
        self.assertEqual(response["results"], [])
        self.assertEqual(live.search_calls, [])

    def test_plugin_can_configure_magnus_without_echoing_credentials(self):
        magnus = FakeMagnus(False)
        live = FakeLive()
        broker = Broker(
            self.state,
            config_file=self.config,
            magnus=magnus,
            live=live,
        )
        response = broker.handle(
            {
                "op": "magnus_configure",
                "domain": "rock.example.org",
                "username": "rock-user",
                "password": "private-password",
            }
        )
        self.assertTrue(response["ok"])
        self.assertTrue(response["refreshLive"])
        self.assertEqual(magnus.saved, ("rock-user", "private-password"))
        self.assertEqual(magnus.server, DEFAULT_ROCK_ORIGIN)
        self.assertEqual(InstanceStore(self.instance).get(), DEFAULT_ROCK_ORIGIN)
        serialized = json.dumps(response)
        self.assertNotIn("rock-user", serialized)
        self.assertNotIn("private-password", serialized)

    def test_personal_links_and_quick_returns_open_only_by_safe_id(self):
        InstanceStore(self.instance).set(DEFAULT_ROCK_ORIGIN)
        opened = []
        live = FakeLive()
        broker = Broker(
            self.state,
            config_file=self.config,
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

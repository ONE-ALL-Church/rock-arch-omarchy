import json
import tempfile
import unittest
from pathlib import Path

from rock_lens_broker.broker import Broker
from rock_lens_broker.contracts import ALLOWED_PERSON_KEYS, ALLOWED_RESULT_KEYS, CATEGORIES


class BrokerContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "context"
        self.broker = Broker(self.state)

    def tearDown(self):
        self.tmp.cleanup()

    def test_context_defaults_dev_and_persists_explicitly(self):
        self.assertEqual(self.broker.handle({"op": "status"})["context"], "DEV")
        self.assertEqual(self.state.read_text(encoding="utf-8"), "DEV\n")
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.broker.handle({"op": "set_context", "context": "PROD"})["context"], "PROD")
        self.assertEqual(Broker(self.state).handle({"op": "status"})["context"], "PROD")

    def test_invalid_context_fails_closed(self):
        self.assertEqual(self.broker.handle({"op": "set_context", "context": "staging"}), {"ok": False, "error": "invalid_context"})

    def test_all_categories_and_allowlisted_search_contract(self):
        response = self.broker.handle({"op": "search", "query": ""})
        self.assertEqual({row["category"] for row in response["results"]}, set(CATEGORIES))
        for row in response["results"]:
            self.assertLessEqual(set(row), ALLOWED_RESULT_KEYS)

    def test_person_quick_look_is_privacy_minimal(self):
        person = self.broker.handle({"op": "person_quick_look", "safeId": "mock-person-ada"})["person"]
        self.assertLessEqual(set(person), ALLOWED_PERSON_KEYS)
        serialized = json.dumps(person).lower()
        for forbidden in ("email", "phone", "address", "birth", "cookie", "token"):
            self.assertNotIn(forbidden, serialized)

    def test_no_mutation_or_job_run_operation(self):
        for op in ("run_job", "run_now", "insert", "update", "delete"):
            self.assertEqual(self.broker.handle({"op": op})["error"], "unsupported_operation")

    def test_live_capabilities_are_not_healthy(self):
        states = {row["name"]: row["state"] for row in self.broker.handle({"op": "status"})["capabilities"]}
        self.assertEqual(states["mock"], "healthy")
        self.assertTrue(all(states[name] != "healthy" for name in ("rock_v3", "sql", "magnus")))


if __name__ == "__main__":
    unittest.main()

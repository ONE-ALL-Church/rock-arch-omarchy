import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rock_lens_broker.build_receipts import (
    MAX_BUILD_RECEIPTS,
    BuildReceiptStore,
)


class BuildReceiptStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "builds.json"
        self.store = BuildReceiptStore(self.path)

    def tearDown(self):
        self.temporary.cleanup()

    def test_receipts_are_private_opaque_and_never_claim_completion(self):
        receipt = self.store.add("Production Mobile")

        self.assertRegex(receipt["buildId"], r"^build-[0-9a-f]{32}$")
        self.assertEqual(receipt["state"], "accepted")
        self.assertFalse(receipt["completionVerifiable"])
        self.assertTrue(receipt["persisted"])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.store.get(receipt["buildId"]), receipt)
        self.assertNotIn("url", json.dumps(receipt).lower())
        self.assertNotIn("complete", receipt["state"])

    def test_store_caps_rows_and_rejects_permissive_external_content(self):
        for index in range(MAX_BUILD_RECEIPTS + 5):
            self.store.add(f"App {index}")
        self.assertEqual(len(self.store.public_items()), MAX_BUILD_RECEIPTS)

        self.path.chmod(0o644)
        self.assertEqual(self.store.public_items(), [])

    def test_a_write_failure_returns_an_explicit_volatile_receipt(self):
        with patch.object(self.store, "_write", side_effect=OSError):
            receipt = self.store.add("Production Mobile")
        self.assertFalse(receipt["persisted"])
        self.assertIsNone(self.store.get(receipt["buildId"]))


if __name__ == "__main__":
    unittest.main()

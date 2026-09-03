import json
import tempfile
import unittest
from pathlib import Path

from rock_lens_broker.contracts import CATEGORIES
from rock_lens_broker.instance import InstanceStore
from rock_lens_broker.origin import DEFAULT_ROCK_ORIGIN
from rock_lens_broker.profiles import ProfileError, ProfileStore


class ProfileStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.instance = InstanceStore(root / "instance.json")
        self.path = root / "profiles.json"

    def tearDown(self):
        self.temporary.cleanup()

    def test_legacy_instance_migrates_to_stable_owner_only_profile(self):
        self.instance.set(DEFAULT_ROCK_ORIGIN)
        store = ProfileStore(self.path, self.instance)
        active = store.active()
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active.origin, DEFAULT_ROCK_ORIGIN)
        self.assertEqual(store.migrated_profile_id, active.profile_id)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        reloaded = ProfileStore(self.path, self.instance).active()
        self.assertIsNotNone(reloaded)
        assert reloaded is not None
        self.assertEqual(reloaded.profile_id, active.profile_id)

    def test_profiles_can_share_an_origin_and_switch_by_id(self):
        store = ProfileStore(self.path, self.instance)
        first = store.add("Staff", DEFAULT_ROCK_ORIGIN)
        second = store.add("Volunteer", DEFAULT_ROCK_ORIGIN)
        self.assertNotEqual(first.profile_id, second.profile_id)
        self.assertEqual(store.active(), second)
        self.assertEqual(store.set_active(first.profile_id), first)
        self.assertTrue(store.snapshot()["profiles"][0]["isActive"])

    def test_preferences_are_allowlisted_and_ordered(self):
        store = ProfileStore(self.path, self.instance)
        updated = store.update_preferences(
            {
                "showPersonContext": False,
                "enabledCategories": ["Groups", "People"],
            }
        )
        self.assertFalse(updated["showPersonContext"])
        self.assertTrue(updated["closeAfterOpen"])
        self.assertEqual(updated["enabledCategories"], ["People", "Groups"])
        with self.assertRaisesRegex(ProfileError, "invalid_preferences"):
            store.update_preferences({"rawCookie": True})
        with self.assertRaisesRegex(ProfileError, "invalid_profile_name"):
            store.add({"unexpected": "record"}, DEFAULT_ROCK_ORIGIN)

    def test_remove_last_profile_clears_legacy_pointer(self):
        store = ProfileStore(self.path, self.instance)
        profile = store.add("Primary", DEFAULT_ROCK_ORIGIN)
        store.remove(profile.profile_id)
        self.assertIsNone(store.active())
        self.assertIsNone(self.instance.get())

    def test_permissive_or_malformed_profile_store_fails_closed(self):
        self.path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "activeProfileId": "",
                    "profiles": [],
                    "preferences": {"enabledCategories": list(CATEGORIES)},
                }
            ),
            encoding="utf-8",
        )
        self.path.chmod(0o644)
        store = ProfileStore(self.path, self.instance)
        with self.assertRaisesRegex(ProfileError, "profile_store_unavailable"):
            store.snapshot()

        self.path.write_bytes(b"[" * 10_000 + b"]" * 10_000)
        self.path.chmod(0o600)
        with self.assertRaisesRegex(ProfileError, "profile_store_unavailable"):
            store.snapshot()


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from rock_arch_broker.contracts import CATEGORIES
from rock_arch_broker.instance import InstanceStore
from rock_arch_broker.origin import DEFAULT_ROCK_ORIGIN
from rock_arch_broker.profiles import (
    PROFILE_STORE_VERSION,
    ProfileError,
    ProfileStore,
)


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
        self.assertTrue(updated["terminalAccess"])
        self.assertFalse(updated["automaticUpdates"])
        self.assertFalse(updated["automaticUpdatesPrompted"])
        self.assertFalse(updated["onboardingSetupCompleted"])
        self.assertTrue(updated["showMenuBar"])
        self.assertEqual(updated["enabledCategories"], ["People", "Groups"])

        enabled = store.update_preferences({"automaticUpdates": True})
        self.assertTrue(enabled["automaticUpdates"])
        self.assertTrue(enabled["automaticUpdatesPrompted"])

        declined = store.update_preferences(
            {
                "automaticUpdates": False,
                "automaticUpdatesPrompted": True,
            }
        )
        self.assertFalse(declined["automaticUpdates"])
        self.assertTrue(declined["automaticUpdatesPrompted"])
        terminal_disabled = store.update_preferences({"terminalAccess": False})
        self.assertFalse(terminal_disabled["terminalAccess"])
        with self.assertRaisesRegex(ProfileError, "invalid_preferences"):
            store.update_preferences({"rawCookie": True})
        with self.assertRaisesRegex(ProfileError, "invalid_profile_name"):
            store.add({"unexpected": "record"}, DEFAULT_ROCK_ORIGIN)

    def test_tab_order_persists_and_invalid_batch_is_atomic(self):
        store = ProfileStore(self.path, self.instance)
        order = ["knowledge", "search", "magnus", "personal"]
        store.update_preferences({"tabOrder": order})
        self.assertEqual(ProfileStore(self.path, self.instance).preferences()["tabOrder"], order)
        before = self.path.read_bytes()
        for invalid in ([], ["search"] * 4, ["search", "personal", "knowledge", "unknown"],
                        "search", [None, "personal", "knowledge", "magnus"]):
            with self.subTest(order=invalid), self.assertRaisesRegex(ProfileError, "invalid_preferences"):
                store.update_preferences({"recentLinks": False, "tabOrder": invalid})
            self.assertEqual(self.path.read_bytes(), before)

    def test_existing_preferences_gain_default_tab_order(self):
        store = ProfileStore(self.path, self.instance)
        store.update_preferences({"recentLinks": False})
        saved = json.loads(self.path.read_text())
        saved["preferences"].pop("tabOrder")
        saved["preferences"].pop("personalLinksView")
        saved["preferences"].pop("personalLinksExpandedGroups")
        self.path.write_text(json.dumps(saved))
        preferences = ProfileStore(self.path, self.instance).preferences()
        self.assertEqual(preferences["tabOrder"], ["search", "personal", "knowledge", "magnus"])
        self.assertFalse(preferences["recentLinks"])
        self.assertEqual(preferences["personalLinksView"], "sections")
        self.assertEqual(preferences["personalLinksExpandedGroups"], {})

    def test_link_views_and_account_expansion_survive_restart_and_profile_removal(self):
        store = ProfileStore(self.path, self.instance)
        first = store.add("First", DEFAULT_ROCK_ORIGIN)
        second = store.add("Second", DEFAULT_ROCK_ORIGIN)
        groups = {first.profile_id: ["link-group-" + "a" * 32], second.profile_id: ["link-group-" + "b" * 32]}
        store.update_preferences({"personalLinksView": "alpha", "personalLinksExpandedGroups": groups})
        reloaded = ProfileStore(self.path, self.instance)
        self.assertEqual(reloaded.preferences()["personalLinksView"], "alpha")
        self.assertEqual(reloaded.preferences()["personalLinksExpandedGroups"], groups)
        reloaded.remove(first.profile_id)
        self.assertEqual(reloaded.preferences()["personalLinksExpandedGroups"], {second.profile_id: groups[second.profile_id]})

    def test_legacy_groups_view_becomes_sections_without_losing_preferences(self):
        store = ProfileStore(self.path, self.instance)
        profile = store.add("Primary", DEFAULT_ROCK_ORIGIN)
        expanded = {profile.profile_id: ["link-group-" + "a" * 32]}
        store.update_preferences({"personalLinksExpandedGroups": expanded, "recentLinks": False})
        saved = json.loads(self.path.read_text())
        saved["preferences"]["personalLinksView"] = "groups"
        self.path.write_text(json.dumps(saved))

        reloaded = ProfileStore(self.path, self.instance)
        self.assertEqual(reloaded.preferences()["personalLinksView"], "sections")
        self.assertEqual(reloaded.preferences()["personalLinksExpandedGroups"], expanded)
        self.assertFalse(reloaded.preferences()["recentLinks"])
        for value in ("sections", "alpha", "groups"):
            reloaded.update_preferences({"personalLinksView": value})
            actual = ProfileStore(self.path, self.instance).preferences()
            self.assertEqual(actual["personalLinksView"], "alpha" if value == "alpha" else "sections")
            self.assertEqual(actual["personalLinksExpandedGroups"], expanded)

    def test_invalid_link_view_or_expansion_batch_preserves_preferences(self):
        store = ProfileStore(self.path, self.instance)
        profile = store.add("Primary", DEFAULT_ROCK_ORIGIN)
        before = self.path.read_bytes()
        group = "link-group-" + "a" * 32
        updates = [{"personalLinksView": value} for value in ("newest", "", [], {}, None, True)]
        updates += [{"personalLinksExpandedGroups": value} for value in (
            [], {"unknown-profile": [group]}, {profile.profile_id: "all"},
            {profile.profile_id: [group, group]}, {profile.profile_id: [42]},
            {profile.profile_id: ["raw-section-id"]},
            {profile.profile_id: ["link-group-" + f"{number:032x}" for number in range(151)]},
        )]
        for update in updates:
            with self.subTest(update=update), self.assertRaisesRegex(ProfileError, "invalid_preferences"):
                store.update_preferences({"recentLinks": False, **update})
            self.assertEqual(self.path.read_bytes(), before)

    def test_version_one_preferences_gain_new_search_categories_once(self):
        self.path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "activeProfileId": "",
                    "profiles": [],
                    "preferences": {
                        "automaticUpdatesPrompted": True,
                        "enabledCategories": ["People", "Groups"],
                    },
                }
            ),
            encoding="utf-8",
        )
        self.path.chmod(0o600)
        store = ProfileStore(self.path, self.instance)

        snapshot = store.snapshot()

        self.assertTrue(snapshot["preferences"]["onboardingSetupCompleted"])
        self.assertEqual(
            snapshot["preferences"]["enabledCategories"],
            ["People", "Groups", "Group Types", "Defined Types", "Content Channel Types"],
        )
        store.update_preferences(
            {"enabledCategories": ["People", "Content Channel Types"]}
        )
        persisted = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["version"], PROFILE_STORE_VERSION)
        self.assertEqual(
            store.preferences()["enabledCategories"],
            ["People", "Content Channel Types"],
        )

    def test_version_two_gains_defined_types_once_and_preserves_disabled_categories(self):
        self.path.write_text(json.dumps({
            "version": 2, "activeProfileId": "", "profiles": [],
            "preferences": {"enabledCategories": ["People"], "terminalMutationAccess": False},
        }))
        self.path.chmod(0o600)
        store = ProfileStore(self.path, self.instance)
        self.assertEqual(store.preferences()["enabledCategories"], ["People", "Defined Types"])
        self.assertFalse(store.preferences()["terminalMutationAccess"])
        store.update_preferences({"enabledCategories": ["People"]})
        reopened = ProfileStore(self.path, self.instance)
        self.assertEqual(reopened.preferences()["enabledCategories"], ["People"])
        self.assertEqual(json.loads(self.path.read_text())["version"], PROFILE_STORE_VERSION)

    def test_profile_name_can_be_changed_without_changing_its_identity(self):
        store = ProfileStore(self.path, self.instance)
        profile = store.add("Production", DEFAULT_ROCK_ORIGIN)

        renamed = store.rename(profile.profile_id, "Rock Solid Church Production")

        self.assertEqual(renamed.profile_id, profile.profile_id)
        self.assertEqual(renamed.origin, profile.origin)
        self.assertEqual(renamed.name, "Rock Solid Church Production")

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

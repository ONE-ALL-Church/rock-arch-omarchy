import json
import tempfile
import unittest
from pathlib import Path

from rock_lens_broker.navigation import NavigationTarget
from rock_lens_broker.origin import DEFAULT_ROCK_ORIGIN
from rock_lens_broker.quick_return import MAX_QUICK_RETURNS, QuickReturnStore


class QuickReturnTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "state" / "quick-returns.json"
        self.store = QuickReturnStore(self.path, DEFAULT_ROCK_ORIGIN)

    def tearDown(self):
        self.temporary.cleanup()

    def test_store_is_owner_only_opaque_and_resolvable(self):
        self.store.add(
            NavigationTarget(
                "Ada Rivera",
                "Person",
                10,
                "https://rock.example.org/Person/17",
            )
        )
        items = self.store.public_items()
        self.assertEqual(items[0]["title"], "Ada Rivera")
        self.assertRegex(items[0]["lastUsedAt"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertNotIn("url", json.dumps(items).lower())
        self.assertEqual(self.path.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        target = self.store.resolve(items[0]["safeId"])
        self.assertIsNotNone(target)
        assert target is not None
        self.assertEqual(target.url, "https://rock.example.org/Person/17")

    def test_deduplicates_and_caps_at_twenty(self):
        first = NavigationTarget(
            "Ada", "Person", 10, "https://rock.example.org/Person/1"
        )
        self.store.add(first)
        self.store.add(first)
        self.assertEqual(len(self.store.public_items()), 1)
        for number in range(MAX_QUICK_RETURNS + 5):
            self.store.add(
                NavigationTarget(
                    f"Person {number}",
                    "Person",
                    10,
                    f"https://rock.example.org/Person/{number + 20}",
                )
            )
        self.assertEqual(len(self.store.public_items()), MAX_QUICK_RETURNS)

    def test_public_items_are_globally_sorted_by_last_used(self):
        self.store._write(
            [
                {
                    "title": "Older person",
                    "kind": "Person",
                    "typeOrder": 10,
                    "url": DEFAULT_ROCK_ORIGIN + "/Person/1",
                    "createdDateTime": "2026-09-02T10:00:00+00:00",
                },
                {
                    "title": "Newest page",
                    "kind": "Page",
                    "typeOrder": 50,
                    "url": DEFAULT_ROCK_ORIGIN + "/page/2",
                    "createdDateTime": "2026-09-02T12:00:00+00:00",
                },
                {
                    "title": "Middle group",
                    "kind": "Group",
                    "typeOrder": 20,
                    "url": DEFAULT_ROCK_ORIGIN + "/Group/3",
                    "createdDateTime": "2026-09-02T11:00:00+00:00",
                },
            ]
        )

        self.assertEqual(
            [item["title"] for item in self.store.public_items()],
            ["Newest page", "Middle group", "Older person"],
        )

    def test_reopening_an_item_moves_it_to_the_top(self):
        self.store._write(
            [
                {
                    "title": "Person",
                    "kind": "Person",
                    "typeOrder": 10,
                    "url": DEFAULT_ROCK_ORIGIN + "/Person/1",
                    "createdDateTime": "2000-01-01T00:00:00+00:00",
                },
                {
                    "title": "Group",
                    "kind": "Group",
                    "typeOrder": 20,
                    "url": DEFAULT_ROCK_ORIGIN + "/Group/2",
                    "createdDateTime": "2001-01-01T00:00:00+00:00",
                },
            ]
        )

        self.store.add(
            NavigationTarget(
                "Person",
                "Person",
                10,
                DEFAULT_ROCK_ORIGIN + "/Person/1",
            )
        )

        self.assertEqual(
            [item["title"] for item in self.store.public_items()],
            ["Person", "Group"],
        )
        self.assertEqual(len(self.store.public_items()), 2)

    def test_invalid_external_rows_are_ignored(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            json.dumps(
                [
                    {
                        "title": "Bad",
                        "kind": "Person",
                        "typeOrder": 10,
                        "url": "https://attacker.example/",
                        "createdDateTime": "2026-09-02T00:00:00+00:00",
                    }
                ]
            ),
            encoding="utf-8",
        )
        self.path.chmod(0o600)
        self.assertEqual(self.store.public_items(), [])

    def test_permissive_store_is_rejected(self):
        self.store.add(
            NavigationTarget(
                "People",
                "Page",
                50,
                DEFAULT_ROCK_ORIGIN + "/page/12",
            )
        )
        self.path.chmod(0o644)
        self.assertEqual(self.store.public_items(), [])

    def test_clear_removes_only_the_local_history_file(self):
        self.store.add(
            NavigationTarget(
                "People",
                "Page",
                50,
                DEFAULT_ROCK_ORIGIN + "/page/12",
            )
        )
        self.assertTrue(self.path.exists())
        self.store.clear()
        self.assertFalse(self.path.exists())
        self.assertEqual(self.store.public_items(), [])


if __name__ == "__main__":
    unittest.main()

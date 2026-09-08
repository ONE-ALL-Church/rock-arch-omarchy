import copy
import io
import json
import re
import tempfile
import unittest
import urllib.error
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from test_broker import FakeLive, FakeMagnus, FakeSession

from rock_arch_broker.broker import Broker
from rock_arch_broker.cli import CliError, _parser, _request
from rock_arch_broker.contracts import Context
from rock_arch_broker.instance import InstanceStore
from rock_arch_broker.navigation import NavigationTarget
from rock_arch_broker.personal_links import (
    CURRENT_PERSON,
    LINKS,
    MAX_RESPONSE,
    MAX_SECTION_LINKS,
    NEW_SECTION,
    SECTIONS,
    PersonalLinkError,
    PersonalLinkHttpClient,
    PersonalLinkManager,
)
from rock_arch_broker.terminal_access import CLI_CLIENT

ORIGIN = "https://rock.example.org"


class Cookie:
    @contextmanager
    def authenticated_cookie(self):
        yield ".ROCK=test-session"


class FakeRock:
    def __init__(self):
        self.person = {"Id": 42, "PrimaryAliasId": 420, "Email": "private@example.org"}
        self.sections = [
            {"Id": 7, "Name": "Work", "IsShared": False, "PersonAliasId": 420}
        ]
        self.links = []
        self.calls = []
        self.lose_response = False
        self.lose_section_response = False
        self.corrupt_section_readback = False
        self.corrupt_readback = False
        self.keep_deleted = False
        self.lose_delete = False
        self.keep_children = False

    @property
    def writes(self):
        return [call for call in self.calls if call[0] in ("POST", "DELETE")]

    def get(self, origin, path, params, cookie):
        self.calls.append(("GET", path, copy.deepcopy(params)))
        if path == CURRENT_PERSON:
            return dict(self.person)
        if path == SECTIONS:
            sections = copy.deepcopy(self.sections)
            match = re.fullmatch(r"Id eq (\d+)", params["$filter"])
            if match:
                return [s for s in sections if s["Id"] == int(match[1])]
            if self.corrupt_section_readback and self.writes:
                sections[-1]["Name"] = "Unexpected section"
            return sections
        condition = params["$filter"]
        match = re.search(r"(?:^|and )Id eq (\d+)", condition)
        if match:
            rows = [dict(item) for item in self.links if item["Id"] == int(match[1])]
            if rows and self.corrupt_readback:
                rows[0]["SectionId"] = 999
            return rows
        match = re.fullmatch(r"SectionId eq (\d+)", condition)
        if match:
            return [
                dict(item) for item in self.links if item["SectionId"] == int(match[1])
            ][: int(params.get("$top", "1"))]
        match = re.search(r"and SectionId eq (\d+) and Url eq '(.*)'$", condition)
        return [
            dict(item)
            for item in self.links
            if item["SectionId"] == int(match[1])
            and item["Url"] == match[2].replace("''", "'")
        ][:1]

    def create(self, origin, path, body, cookie):
        self.calls.append(("POST", path, copy.deepcopy(body)))
        if path == SECTIONS:
            number = max([8] + [section["Id"] for section in self.sections]) + 1
            self.sections.append(
                {
                    "Id": number,
                    "Name": body["Name"],
                    "IsShared": body["IsShared"],
                    "PersonAliasId": body["PersonAliasId"],
                }
            )
            if self.lose_section_response:
                raise PersonalLinkError("personal_link_save_uncertain")
            return number
        self.links.append({"Id": 100 + len(self.links), **body})
        if self.lose_response:
            raise PersonalLinkError("personal_link_save_uncertain")
        return self.links[-1]["Id"]

    def delete(self, origin, path, number, cookie):
        self.calls.append(("DELETE", path, number))
        if not self.keep_deleted:
            if path == LINKS:
                self.links = [item for item in self.links if item["Id"] != number]
            else:
                self.sections = [item for item in self.sections if item["Id"] != number]
                if not self.keep_children:
                    self.links = [
                        item for item in self.links if item["SectionId"] != number
                    ]
        if self.lose_delete:
            raise PersonalLinkError("personal_delete_uncertain")


class PersonalLinkTests(unittest.TestCase):
    def setUp(self):
        self.rock = FakeRock()
        self.manager = PersonalLinkManager(Cookie(), self.rock)
        self.manager.set_origin(ORIGIN)

    def draft(self):
        return self.manager.prepare("People", "/page/42")

    def test_explicit_section_creation_is_private_confirmed_and_read_back(self):
        draft = self.manager.prepare_section("  Projects  ")
        self.assertEqual(self.rock.writes, [])
        self.assertEqual(draft["name"], "Projects")
        result = self.manager.save_section(
            draft["draftId"], draft["name"], confirmed=True
        )
        self.assertTrue(result["saved"])
        self.assertFalse(result["alreadySaved"])
        self.assertEqual(
            self.rock.writes,
            [
                (
                    "POST",
                    SECTIONS,
                    {"Name": "Projects", "PersonAliasId": 420, "IsShared": False},
                )
            ],
        )
        self.assertTrue(result["sectionId"].startswith("link-section-"))
        with self.assertRaisesRegex(PersonalLinkError, "draft_expired"):
            self.manager.save_section(draft["draftId"], draft["name"], confirmed=True)

    def test_section_duplicate_reuses_case_insensitive_name(self):
        draft = self.manager.prepare_section(" work ")
        result = self.manager.save_section(
            draft["draftId"], draft["name"], confirmed=True
        )
        self.assertTrue(result["alreadySaved"])
        self.assertEqual(result["name"], "Work")
        self.assertEqual(self.rock.writes, [])

    def test_lost_section_response_can_be_checked_then_retried_without_duplicate(self):
        self.rock.lose_section_response = True
        draft = self.manager.prepare_section("Projects")
        with self.assertRaisesRegex(PersonalLinkError, "save_uncertain"):
            self.manager.save_section(draft["draftId"], draft["name"], confirmed=True)
        self.rock.lose_section_response = False
        retry = self.manager.prepare_section("Projects")
        result = self.manager.save_section(
            retry["draftId"], retry["name"], confirmed=True
        )
        self.assertTrue(result["alreadySaved"])
        self.assertEqual(len(self.rock.writes), 1)

    def test_section_confirmation_name_and_draft_kind_prevent_unintended_writes(self):
        draft = self.manager.prepare_section("Projects")
        with self.assertRaisesRegex(PersonalLinkError, "confirmation_required"):
            self.manager.save_section(draft["draftId"], "Projects", confirmed=False)
        for name in ("", " ", "x" * 101, "bad\nname", "\udcff", None):
            with (
                self.subTest(name=repr(name)),
                self.assertRaisesRegex(PersonalLinkError, "name_invalid"),
            ):
                self.manager.save_section(draft["draftId"], name, confirmed=True)
        link = self.draft()
        with self.assertRaisesRegex(PersonalLinkError, "draft_expired"):
            self.manager.save_section(link["draftId"], "Projects", confirmed=True)
        with self.assertRaisesRegex(PersonalLinkError, "draft_expired"):
            self.manager.save(
                draft["draftId"], "Page", "/page/42", None, confirmed=True
            )
        self.assertEqual(self.rock.writes, [])

    def test_section_account_change_or_expiration_never_writes(self):
        draft = self.manager.prepare_section("Projects")
        self.rock.person["PrimaryAliasId"] = 421
        with self.assertRaisesRegex(PersonalLinkError, "account_changed"):
            self.manager.save_section(draft["draftId"], "Projects", confirmed=True)
        self.assertFalse(self.manager._drafts)
        self.rock.person["PrimaryAliasId"] = 420
        draft = self.manager.prepare_section("Projects")
        with (
            patch(
                "rock_arch_broker.personal_links.time.monotonic",
                return_value=float("inf"),
            ),
            self.assertRaisesRegex(PersonalLinkError, "draft_expired"),
        ):
            self.manager.save_section(draft["draftId"], "Projects", confirmed=True)
        self.assertEqual(self.rock.writes, [])

    def test_section_readback_mismatch_never_reports_success(self):
        draft = self.manager.prepare_section("Projects")
        self.rock.corrupt_section_readback = True
        with self.assertRaisesRegex(PersonalLinkError, "save_uncertain"):
            self.manager.save_section(draft["draftId"], "Projects", confirmed=True)
        self.assertEqual(len(self.rock.writes), 1)

    def test_section_limit_refuses_creation_before_post(self):
        self.rock.sections = [
            {
                "Id": i + 1,
                "Name": f"Section {i}",
                "IsShared": False,
                "PersonAliasId": 420,
            }
            for i in range(100)
        ]
        draft = self.manager.prepare_section("New section")
        with self.assertRaisesRegex(PersonalLinkError, "personal_section_limit"):
            self.manager.save_section(draft["draftId"], "New section", confirmed=True)
        self.assertEqual(self.rock.writes, [])

    def save(self, draft, **overrides):
        return self.manager.save(
            **{
                "draft_id": draft["draftId"],
                "name": draft["name"],
                "url": draft["url"],
                "section_id": draft["sectionId"],
                "confirmed": True,
                **overrides,
            }
        )

    def test_prepare_is_read_only_and_only_exposes_form_metadata(self):
        draft = self.draft()
        self.assertEqual(self.rock.writes, [])
        self.assertEqual(draft["url"], ORIGIN + "/page/42")
        self.assertEqual(set(draft["sections"][0]), {"safeId", "name"})
        self.assertNotIn("private@example.org", json.dumps(draft))
        self.assertTrue(draft["sectionId"].startswith("link-section-"))
        query = self.rock.calls[-1][2]
        self.assertIn("PersonAliasId eq 420", query["$filter"])
        self.assertEqual(query["$top"], "101")

    def test_confirmed_save_rechecks_owner_and_reads_back_exact_record(self):
        draft = self.draft()
        result = self.save(draft)
        self.assertTrue(result["saved"])
        self.assertFalse(result["alreadySaved"])
        self.assertEqual(
            self.rock.writes,
            [
                (
                    "POST",
                    LINKS,
                    {
                        "Name": "People",
                        "Url": ORIGIN + "/page/42",
                        "PersonAliasId": 420,
                        "SectionId": 7,
                        "Order": 0,
                    },
                )
            ],
        )
        self.assertIn("and Id eq 100", self.rock.calls[-1][2]["$filter"])
        with self.assertRaisesRegex(PersonalLinkError, "draft_expired"):
            self.save(draft)
        self.assertEqual(len(self.rock.writes), 1)

    def test_duplicate_does_not_create_another_link(self):
        self.save(self.draft())
        result = self.save(self.draft())
        self.assertTrue(result["alreadySaved"])
        self.assertEqual(len(self.rock.writes), 1)

    def test_empty_account_creates_only_a_private_default_section_on_save(self):
        self.rock.sections = []
        draft = self.draft()
        self.assertEqual(draft["sectionId"], NEW_SECTION)
        self.assertFalse(self.rock.writes)
        self.save(draft)
        self.assertEqual(
            self.rock.writes[0],
            (
                "POST",
                SECTIONS,
                {
                    "Name": "Links",
                    "PersonAliasId": 420,
                    "IsShared": False,
                },
            ),
        )
        self.assertEqual(self.rock.writes[1][2]["SectionId"], 9)

    def test_new_default_reuses_section_created_since_prepare(self):
        self.rock.sections = []
        draft = self.draft()
        self.rock.sections = [
            {"Id": 9, "Name": "Links", "IsShared": False, "PersonAliasId": 420}
        ]
        self.save(draft)
        self.assertEqual([item[1] for item in self.rock.writes], [LINKS])

    def test_invalid_fields_and_missing_confirmation_never_write(self):
        draft = self.draft()
        for changes in (
            {"confirmed": False},
            {"name": " "},
            {"name": "x" * 101},
            {"name": "😀" * 51},
            {"name": "bad\nname"},
            {"url": "https://evil.example/page/1"},
            {"url": "javascript:alert(1)"},
            {"url": "//evil.example/a"},
            {"url": "https://rock.example.org:444/a"},
            {"url": "https://user@rock.example.org/a"},
            {"section_id": "7"},
            {"section_id": "link-section-forged"},
        ):
            with self.subTest(changes=changes), self.assertRaises(PersonalLinkError):
                self.save(draft, **changes)
        self.assertEqual(self.rock.writes, [])

    def test_shared_foreign_and_malformed_sections_fail_closed(self):
        for change in (
            {"IsShared": True},
            {"IsShared": 0},
            {"PersonAliasId": 990},
            {"Id": True},
        ):
            self.rock.sections = [
                {
                    "Id": 7,
                    "Name": "Work",
                    "IsShared": False,
                    "PersonAliasId": 420,
                    **change,
                }
            ]
            with (
                self.subTest(change=change),
                self.assertRaisesRegex(PersonalLinkError, "sections_invalid"),
            ):
                self.draft()
        self.assertEqual(self.rock.writes, [])

    def test_deleted_section_and_changed_account_do_not_write(self):
        draft = self.draft()
        self.rock.sections = []
        with self.assertRaisesRegex(PersonalLinkError, "section_changed"):
            self.save(draft)
        self.rock.person = {"Id": 99, "PrimaryAliasId": 990}
        with self.assertRaisesRegex(PersonalLinkError, "account_changed"):
            self.save(draft)
        self.assertEqual(self.rock.writes, [])

    def test_profile_clear_and_expiry_invalidate_drafts(self):
        draft = self.draft()
        self.manager.set_origin("https://other.example.org")
        with self.assertRaisesRegex(PersonalLinkError, "draft_expired"):
            self.save(draft)
        with patch("rock_arch_broker.personal_links.time.monotonic", return_value=100):
            draft = self.draft()
        with (
            patch("rock_arch_broker.personal_links.time.monotonic", return_value=701),
            self.assertRaisesRegex(PersonalLinkError, "draft_expired"),
        ):
            self.save(draft)
        self.assertEqual(self.rock.writes, [])

    def test_lost_post_response_is_not_replayed_and_explicit_retry_finds_duplicate(
        self,
    ):
        draft = self.draft()
        self.rock.lose_response = True
        with self.assertRaisesRegex(PersonalLinkError, "save_uncertain"):
            self.save(draft)
        with self.assertRaisesRegex(PersonalLinkError, "draft_expired"):
            self.save(draft)
        self.assertTrue(self.save(self.draft())["alreadySaved"])
        self.assertEqual(len(self.rock.writes), 1)

    def test_readback_mismatch_is_never_reported_as_saved(self):
        self.rock.corrupt_readback = True
        with self.assertRaisesRegex(PersonalLinkError, "save_uncertain"):
            self.save(self.draft())

    def test_quote_in_url_is_escaped_in_fixed_duplicate_query(self):
        self.save(self.manager.prepare("A quote", "/page/42?q=O'Brien"))
        filters = [
            call[2].get("$filter", "") for call in self.rock.calls if call[0] == "GET"
        ]
        self.assertTrue(any("O''Brien" in query for query in filters))


class PersonalDeleteTests(unittest.TestCase):
    def setUp(self):
        self.rock = FakeRock()
        self.manager = PersonalLinkManager(Cookie(), self.rock)
        self.manager.set_origin(ORIGIN)
        self.link = {
            "Id": 100,
            "Name": "Page",
            "Url": ORIGIN + "/page/42",
            "SectionId": 7,
            "PersonAliasId": 420,
        }
        self.rock.links = [dict(self.link)]

    def prepare(self, kind="link", *, with_links=False):
        target = 100 if kind == "link" else self.manager.list_sections()[0]["safeId"]
        return self.manager.prepare_delete(kind, target, with_links=with_links)

    def test_confirmed_link_delete_uses_exact_record_and_verifies_absence(self):
        draft = self.prepare()
        self.assertEqual(self.rock.writes, [])
        self.assertNotIn("PersonAliasId", json.dumps(draft))
        with self.assertRaisesRegex(PersonalLinkError, "confirmation_required"):
            self.manager.delete(draft["draftId"], confirmed=False)
        result = self.manager.delete(draft["draftId"], confirmed=True)
        self.assertTrue(result["deleted"])
        self.assertFalse(result["alreadyDeleted"])
        self.assertEqual(self.rock.writes, [("DELETE", LINKS, 100)])
        with self.assertRaisesRegex(PersonalLinkError, "draft_expired"):
            self.manager.delete(draft["draftId"], confirmed=True)

    def test_empty_section_deleted_only_after_unfiltered_child_recheck(self):
        self.rock.links = []
        draft = self.prepare("section")
        self.manager.delete(draft["draftId"], confirmed=True)
        self.assertEqual(self.rock.writes, [("DELETE", SECTIONS, 7)])
        child_reads = [call for call in self.rock.calls if call[:2] == ("GET", LINKS)]
        self.assertEqual(len(child_reads), 3)
        self.assertEqual(
            child_reads[0][2],
            {
                "$filter": "SectionId eq 7",
                "$select": "Id,SectionId",
                "$orderby": "Id",
                "$top": str(MAX_SECTION_LINKS + 1),
            },
        )
        self.assertTrue(
            all(
                call[2] == {"$filter": "SectionId eq 7", "$select": "Id", "$top": "1"}
                for call in child_reads[1:]
            )
        )

    def test_with_links_counts_all_children_and_verifies_cascade_with_one_delete(self):
        self.rock.links += [
            {
                **self.link,
                "Id": 101,
                "Url": "https://other.example/hidden",
                "PersonAliasId": 999,
            }
        ]
        draft = self.prepare("section", with_links=True)
        self.assertEqual(draft["linkCount"], 2)
        self.assertTrue(draft["withLinks"])
        self.assertNotIn("link_ids", draft)
        self.assertNotIn("PersonAliasId", json.dumps(draft))
        self.assertEqual(self.rock.writes, [])
        result = self.manager.delete(draft["draftId"], confirmed=True, with_links=True)
        self.assertEqual(result["linkCount"], 2)
        self.assertTrue(result["withLinks"])
        self.assertEqual(self.rock.links, [])
        self.assertEqual(self.rock.writes, [("DELETE", SECTIONS, 7)])

    def test_with_links_scope_is_explicit_and_bound_to_draft(self):
        draft = self.prepare("section", with_links=True)
        with self.assertRaisesRegex(PersonalLinkError, "scope_invalid"):
            self.manager.delete(draft["draftId"], confirmed=True)
        with self.assertRaisesRegex(PersonalLinkError, "confirmation_required"):
            self.manager.delete(draft["draftId"], confirmed=False, with_links=True)
        self.rock.links = []
        empty = self.prepare("section")
        with self.assertRaisesRegex(PersonalLinkError, "scope_invalid"):
            self.manager.delete(empty["draftId"], confirmed=True, with_links=True)
        for flag in (1, "true", None):
            with self.assertRaisesRegex(PersonalLinkError, "scope_invalid"):
                self.prepare("section", with_links=flag)
        with self.assertRaisesRegex(PersonalLinkError, "scope_invalid"):
            self.prepare(with_links=True)
        self.assertEqual(self.rock.writes, [])

    def test_with_links_requires_new_review_for_changed_child_ids_even_same_count(self):
        for records in (
            [],
            [{**self.link, "Id": 101}],
            [self.link, {**self.link, "Id": 101}],
        ):
            self.rock.links = [dict(self.link)]
            draft = self.prepare("section", with_links=True)
            self.rock.links = records
            with self.assertRaisesRegex(PersonalLinkError, "contents_changed"):
                self.manager.delete(draft["draftId"], confirmed=True, with_links=True)
        self.assertEqual(self.rock.writes, [])

    def test_count_refuses_truncated_invalid_duplicate_or_wrong_section_rows(self):
        for rows in (
            [self.link] * (MAX_SECTION_LINKS + 1),
            [self.link, self.link],
            [{"Id": True, "SectionId": 7}],
            [{"Id": 100, "SectionId": 8}],
            {"value": []},
        ):
            with (
                patch.object(self.rock, "get", return_value=rows),
                self.assertRaisesRegex(PersonalLinkError, "count_unavailable"),
            ):
                self.manager._section_links(7, ".ROCK=test")
        self.assertEqual(self.rock.writes, [])

    def test_missing_cascade_never_reports_success(self):
        draft = self.prepare("section", with_links=True)
        self.rock.keep_children = True
        with self.assertRaisesRegex(PersonalLinkError, "delete_uncertain"):
            self.manager.delete(draft["draftId"], confirmed=True, with_links=True)
        with self.assertRaisesRegex(PersonalLinkError, "draft_expired"):
            self.manager.delete(draft["draftId"], confirmed=True, with_links=True)
        self.assertEqual(self.rock.writes, [("DELETE", SECTIONS, 7)])

    def test_nonempty_section_and_concurrent_new_link_never_delete(self):
        with self.assertRaisesRegex(PersonalLinkError, "section_not_empty"):
            self.prepare("section")
        self.rock.links = []
        draft = self.prepare("section")
        self.rock.links = [
            {**self.link, "PersonAliasId": 999, "Url": "https://other.example/hidden"}
        ]
        with self.assertRaisesRegex(PersonalLinkError, "section_not_empty"):
            self.manager.delete(draft["draftId"], confirmed=True)
        self.assertEqual(self.rock.writes, [])

    def test_changed_target_requires_fresh_review(self):
        for field, value in (
            ("Name", "Renamed"),
            ("Url", ORIGIN + "/other"),
            ("PersonAliasId", 999),
            ("SectionId", 9),
        ):
            self.rock.links = [dict(self.link)]
            draft = self.prepare()
            self.rock.links[0][field] = value
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(PersonalLinkError, "target_changed"),
            ):
                self.manager.delete(draft["draftId"], confirmed=True)
        self.assertEqual(self.rock.writes, [])

    def test_shared_foreign_and_raw_section_targets_never_delete(self):
        for field, value in (("IsShared", True), ("PersonAliasId", 999)):
            self.rock.sections[0][field] = value
            with self.assertRaises(PersonalLinkError):
                self.prepare()
            self.rock.sections[0] = {
                "Id": 7,
                "Name": "Work",
                "PersonAliasId": 420,
                "IsShared": False,
            }
        self.rock.links[0]["PersonAliasId"] = 999
        with self.assertRaisesRegex(PersonalLinkError, "not_owned"):
            self.prepare()
        for target in (7, "7", "link-section-forged"):
            with self.assertRaises(PersonalLinkError):
                self.manager.prepare_delete("section", target)
        self.assertEqual(self.rock.writes, [])

    def test_changed_section_or_account_never_delete(self):
        draft = self.prepare()
        self.rock.sections[0]["Name"] = "Renamed"
        with self.assertRaisesRegex(PersonalLinkError, "target_changed"):
            self.manager.delete(draft["draftId"], confirmed=True)
        self.rock.person["Id"] = 99
        with self.assertRaisesRegex(PersonalLinkError, "account_changed"):
            self.manager.delete(draft["draftId"], confirmed=True)
        self.assertFalse(self.manager._deletions)
        self.assertEqual(self.rock.writes, [])

    def test_expired_cleared_or_creation_drafts_cannot_delete(self):
        draft = self.prepare()
        with (
            patch(
                "rock_arch_broker.personal_links.time.monotonic",
                return_value=float("inf"),
            ),
            self.assertRaisesRegex(PersonalLinkError, "draft_expired"),
        ):
            self.manager.delete(draft["draftId"], confirmed=True)
        create = self.manager.prepare("Page", "/page/42")
        with self.assertRaisesRegex(PersonalLinkError, "draft_expired"):
            self.manager.delete(create["draftId"], confirmed=True)
        self.manager.clear()
        with self.assertRaisesRegex(PersonalLinkError, "draft_expired"):
            self.manager.delete(draft["draftId"], confirmed=True)
        self.assertEqual(self.rock.writes, [])

    def test_delete_failure_and_readback_failure_are_never_replayed(self):
        for option in ("keep_deleted", "lose_delete"):
            self.setUp()
            setattr(self.rock, option, True)
            draft = self.prepare()
            with self.assertRaisesRegex(PersonalLinkError, "delete_uncertain"):
                self.manager.delete(draft["draftId"], confirmed=True)
            with self.assertRaisesRegex(PersonalLinkError, "draft_expired"):
                self.manager.delete(draft["draftId"], confirmed=True)
            self.assertEqual(self.rock.writes, [("DELETE", LINKS, 100)])

    def test_already_missing_record_is_verified_without_delete(self):
        draft = self.prepare()
        self.rock.links = []
        result = self.manager.delete(draft["draftId"], confirmed=True)
        self.assertTrue(result["alreadyDeleted"])
        self.assertEqual(self.rock.writes, [])


class Response:
    def __init__(self, raw):
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, maximum):
        return self.raw[:maximum]


class Opener:
    def __init__(self, raw=b"100", status=None):
        self.raw, self.status, self.calls = raw, status, []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if self.status:
            raise urllib.error.HTTPError(
                request.full_url, self.status, "PRIVATE SERVER BODY", {}, None
            )
        return Response(self.raw)


class PersonalLinkHttpTests(unittest.TestCase):
    def setUp(self):
        self.body = {
            "Name": "Page",
            "Url": ORIGIN + "/page/42",
            "SectionId": 7,
            "PersonAliasId": 420,
            "Order": 0,
        }

    def test_delete_only_accepts_exact_positive_ids_and_fixed_paths(self):
        opener = Opener(raw=b"")
        client = PersonalLinkHttpClient(opener)
        client.delete(ORIGIN, LINKS, 100, ".ROCK=test")
        request = opener.calls[0][0]
        self.assertEqual(request.full_url, ORIGIN + LINKS + "/100")
        self.assertEqual(request.get_method(), "DELETE")
        self.assertIsNone(request.data)
        self.assertEqual(request.get_header("Cookie"), ".ROCK=test")
        for number in (True, "100", "1/../People/1", -1, 0, 2**31, 1.5):
            with self.assertRaises(PersonalLinkError):
                client.delete(ORIGIN, LINKS, number, ".ROCK=test")
        with self.assertRaises(PersonalLinkError):
            client.delete(ORIGIN, "/api/People", 100, ".ROCK=test")
        self.assertEqual(len(opener.calls), 1)
        for status in (302, 404, 500):
            with self.assertRaisesRegex(PersonalLinkError, "delete_uncertain"):
                PersonalLinkHttpClient(Opener(status=status)).delete(
                    ORIGIN, LINKS, 100, ".ROCK=test"
                )

    def test_fixed_post_has_cookie_header_and_strict_body(self):
        opener = Opener()
        client = PersonalLinkHttpClient(opener)
        self.assertEqual(client.create(ORIGIN, LINKS, self.body, ".ROCK=test"), 100)
        request, timeout = opener.calls[0]
        self.assertEqual(request.full_url, ORIGIN + LINKS)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Cookie"), ".ROCK=test")
        self.assertEqual(json.loads(request.data), self.body)
        self.assertEqual(timeout, 20)
        for path, body in (
            ("/api/People", self.body),
            (LINKS, {**self.body, "Id": 1}),
            (SECTIONS, {"Name": "Shared", "PersonAliasId": 420, "IsShared": True}),
        ):
            with self.assertRaises(PersonalLinkError):
                client.create(ORIGIN, path, body, ".ROCK=test")
        self.assertEqual(len(opener.calls), 1)

    def test_http_errors_are_stable_and_post_is_never_retried(self):
        for status, expected in (
            (401, "not_authorized"),
            (403, "not_authorized"),
            (404, "not_authorized"),
            (400, "rejected"),
            (302, "uncertain"),
            (500, "uncertain"),
        ):
            opener = Opener(status=status)
            with (
                self.subTest(status=status),
                self.assertRaisesRegex(PersonalLinkError, expected),
            ):
                PersonalLinkHttpClient(opener).create(
                    ORIGIN, LINKS, self.body, ".ROCK=test"
                )
            self.assertEqual(len(opener.calls), 1)

    def test_invalid_or_oversized_post_response_is_uncertain(self):
        for raw in (
            b"true",
            b"0",
            b"[]",
            b"NaN",
            b"not JSON",
            b"x" * (MAX_RESPONSE + 1),
        ):
            with (
                self.subTest(raw=raw[:20]),
                self.assertRaisesRegex(PersonalLinkError, "uncertain"),
            ):
                PersonalLinkHttpClient(Opener(raw)).create(
                    ORIGIN, LINKS, self.body, ".ROCK=test"
                )


class PersonalLinkBrokerCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        folder = Path(self.tmp.name)
        instance = folder / "instance.json"
        InstanceStore(instance).set(ORIGIN)
        self.rock = FakeRock()
        session = FakeSession(True)
        self.live = FakeLive()
        self.live.invalidate_personal_links = lambda: setattr(
            self.live, "invalidated", True
        )
        self.manager = PersonalLinkManager(session, self.rock)
        self.broker = Broker(
            folder / "context",
            instance_file=instance,
            session=session,
            magnus=FakeMagnus(True),
            live=self.live,
            personal_links=self.manager,
            developer_mode=True,
        )
        self.broker._context = Context.PROD
        self.broker._profile_store.update_preferences({
            "terminalMutationAccess": True,
            "terminalMutationActions": ["addLinks", "addSections", "deleteLinks", "deleteSections"],
        })
        self.calls = []

    def request(self, payload):
        self.calls.append(dict(payload))
        result = self.broker.handle({**payload, "client": CLI_CLIENT})
        if not result["ok"]:
            raise CliError(result["error"])
        return result

    def test_bookmark_from_recent_link_prefills_and_rejects_actions_or_expired_ids(self):
        from rock_arch_broker.navigation import NavigationTarget

        self.broker._quick_returns.add(NavigationTarget("Recent page", "Page", 50, ORIGIN + "/page/42"))
        recent = self.broker._quick_returns.public_items()[0]
        result = _request(_parser().parse_args(["links", "add", "--from", recent["safeId"], "--dry-run"]), self)
        self.assertTrue(result["ok"])
        self.assertEqual(self.rock.writes, [])
        prepared = self.request({"op": "personal_link_prepare", "safeId": recent["safeId"]})["personalLink"]
        self.assertEqual(prepared["name"], "Recent page")
        self.assertEqual(prepared["url"], ORIGIN + "/page/42")
        self.broker._quick_returns.clear()
        with self.assertRaisesRegex(CliError, "personal_link_source_invalid"):
            self.request({"op": "personal_link_prepare", "safeId": recent["safeId"]})
        self.broker._quick_returns.add(NavigationTarget("Deploy app", "Magnus Build", 60, ORIGIN + "/Build/mobileapps/1"))
        build = self.broker._quick_returns.public_items()[0]
        with self.assertRaisesRegex(CliError, "personal_link_source_invalid"):
            self.request({"op": "personal_link_prepare", "safeId": build["safeId"]})

    def test_cli_delete_previews_then_confirms_exact_link_and_empty_section(self):
        self.rock.links = [
            {
                "Id": 100,
                "Name": "Page",
                "Url": ORIGIN + "/page/42",
                "SectionId": 7,
                "PersonAliasId": 420,
            }
        ]
        with self.assertRaisesRegex(CliError, "confirmation_required"):
            _request(
                _parser().parse_args(["links", "delete", "link-delete-test"]), self
            )
        self.assertEqual(self.calls, [])
        preview = _request(
            _parser().parse_args(["links", "delete", "link-delete-test", "--dry-run"]),
            self,
        )
        self.assertEqual(preview["dryRun"]["name"], "Page")
        self.assertFalse(preview["dryRun"]["executed"])
        self.assertEqual(self.rock.writes, [])
        result = _request(
            _parser().parse_args(["links", "delete", "link-delete-test", "--confirm"]),
            self,
        )
        self.assertTrue(result["personalDelete"]["deleted"])
        self.assertNotIn("_sectionId", result["personalDelete"])
        section = self.manager.list_sections()[0]["safeId"]
        result = _request(
            _parser().parse_args(["links", "sections", "delete", section, "--confirm"]),
            self,
        )
        self.assertTrue(result["personalDelete"]["deleted"])
        self.assertEqual(
            self.rock.writes, [("DELETE", LINKS, 100), ("DELETE", SECTIONS, 7)]
        )

    def test_cli_populated_section_requires_flag_and_dry_run_reports_complete_count(
        self,
    ):
        self.rock.links = [
            {
                "Id": 100 + index,
                "Name": "Page",
                "Url": ORIGIN + "/page/42",
                "SectionId": 7,
                "PersonAliasId": 420,
            }
            for index in range(3)
        ]
        section = self.manager.list_sections()[0]["safeId"]
        base = ["links", "sections", "delete", section]
        with self.assertRaisesRegex(CliError, "section_not_empty"):
            _request(_parser().parse_args(base + ["--confirm"]), self)
        self.calls.clear()
        with self.assertRaisesRegex(CliError, "confirmation_required"):
            _request(_parser().parse_args(base + ["--with-links"]), self)
        self.assertEqual(self.calls, [])
        preview = _request(
            _parser().parse_args(base + ["--with-links", "--dry-run"]), self
        )["dryRun"]
        self.assertEqual(preview["linkCount"], 3)
        self.assertTrue(preview["withLinks"])
        self.assertIn(
            "deletes_private_section_and_all_links_in_rock", preview["sideEffects"]
        )
        self.assertFalse(preview["executed"])
        self.assertEqual(self.rock.writes, [])
        result = _request(
            _parser().parse_args(base + ["--with-links", "--confirm"]), self
        )["personalDelete"]
        self.assertTrue(result["deleted"])
        self.assertEqual(result["linkCount"], 3)
        self.assertNotIn("_sectionId", result)
        self.assertEqual(self.rock.links, [])

    def test_delete_rejects_navigation_ids_preview_and_disabled_terminal(self):
        for target in ("rock-safe-person", "100", "link-delete-forged"):
            with self.assertRaisesRegex(CliError, "target_invalid"):
                self.request(
                    {
                        "op": "personal_delete_prepare",
                        "kind": "link",
                        "targetId": target,
                    }
                )
        self.broker._context = Context.DEV
        with self.assertRaisesRegex(CliError, "preview_only"):
            self.request(
                {
                    "op": "personal_delete_prepare",
                    "kind": "link",
                    "targetId": "link-delete-test",
                }
            )
        self.broker._context = Context.PROD
        self.broker._profile_store.update_preferences({"terminalAccess": False})
        with self.assertRaisesRegex(CliError, "terminal_access_disabled"):
            self.request(
                {
                    "op": "personal_delete_prepare",
                    "kind": "link",
                    "targetId": "link-delete-test",
                }
            )
        self.assertEqual(self.rock.calls, [])

    def test_cli_dry_run_resolves_source_but_never_posts(self):
        result = _request(
            _parser().parse_args(
                ["links", "add", "--from", "rock-safe-person", "--dry-run"]
            ),
            self,
        )
        self.assertEqual(result["dryRun"]["name"], "Ada Rivera")
        self.assertFalse(result["dryRun"]["executed"])
        self.assertEqual(self.rock.writes, [])

    def test_cli_stdin_add_is_confirmed_and_invalidates_cached_links(self):
        with patch("sys.stdin", io.StringIO('{"name":"Directory","url":"/page/42"}')):
            result = _request(
                _parser().parse_args(["links", "add", "--stdin", "--confirm"]), self
            )
        self.assertTrue(result["personalLink"]["saved"])
        self.assertEqual(
            [call["op"] for call in self.calls],
            ["personal_link_prepare", "personal_link_save"],
        )
        self.assertTrue(self.live.invalidated)

    def test_cli_section_list_includes_empty_sections_without_allocating_a_draft(self):
        result = _request(_parser().parse_args(["links", "sections"]), self)
        section = result["sections"][0]
        self.assertEqual(set(section), {"safeId", "groupId", "name", "isShared"})
        self.assertEqual(section["name"], "Work")
        self.assertFalse(self.manager._drafts)
        self.rock.sections = []
        result = _request(_parser().parse_args(["links", "sections"]), self)
        self.assertEqual(result["sections"], [])
        self.assertIsNone(result["defaultSectionId"])

    def test_cli_section_creation_and_duplicate_return_only_public_metadata(self):
        args = _parser().parse_args(
            ["links", "sections", "add", "--stdin", "--confirm"]
        )
        for expected_duplicate in (False, True):
            with patch("sys.stdin", io.StringIO('{"name":"Projects"}')):
                result = _request(args, self)["personalSection"]
            self.assertEqual(result["alreadySaved"], expected_duplicate)
            self.assertTrue(result["saved"])
            self.assertEqual(
                set(result),
                {"requestId", "saved", "alreadySaved", "name", "sectionId", "groupId"},
            )
            self.assertRegex(result["groupId"], r"^link-group-[a-f0-9]{32}$")
        self.assertEqual(len(self.rock.writes), 1)
        self.assertTrue(self.live.invalidated)

    def test_cli_section_dry_run_and_invalid_inputs_never_write(self):
        with patch("sys.stdin", io.StringIO('{"name":"Projects"}')):
            result = _request(
                _parser().parse_args(
                    ["links", "sections", "add", "--stdin", "--dry-run"]
                ),
                self,
            )
        self.assertFalse(result["dryRun"]["executed"])
        self.assertEqual(self.rock.writes, [])
        self.calls.clear()
        for value in (
            "{}",
            "[]",
            '{"name":" "}',
            '{"name":false}',
            '{"name":"x","IsShared":true}',
            '{"name":"x","PersonAliasId":9}',
            '{"name":"x","url":"/page/42"}',
        ):
            with patch("sys.stdin", io.StringIO(value)), self.assertRaises(CliError):
                _request(
                    _parser().parse_args(
                        ["links", "sections", "add", "--stdin", "--confirm"]
                    ),
                    self,
                )
        with self.assertRaisesRegex(CliError, "confirmation_required"):
            _request(
                _parser().parse_args(["links", "sections", "add", "--stdin"]), self
            )
        self.assertEqual(self.calls, [])

    def test_navigation_catalog_is_optional_and_does_not_expose_raw_identifiers(self):
        result = self.broker.handle({"op": "navigation_status", "section": "personal"})
        self.assertTrue(result["personalLinkSectionsAvailable"])
        self.assertEqual(
            set(result["personalLinkSections"][0]),
            {"safeId", "groupId", "name", "isShared"},
        )
        with patch.object(
            self.manager,
            "list_sections",
            side_effect=PersonalLinkError("personal_links_not_authorized"),
        ):
            result = self.broker.handle(
                {"op": "navigation_status", "section": "personal"}
            )
        self.assertTrue(result["ok"])
        self.assertTrue(result["personalLinksAvailable"])
        self.assertFalse(result["personalLinkSectionsAvailable"])
        self.assertTrue(result["personalLinks"])

    def test_cli_bad_input_and_missing_confirmation_never_reach_broker(self):
        for value in (
            "[]",
            "{}",
            '{"name":"x","url":"/a","PersonAliasId":9}',
            '{"name":"x","url":"/a","safeId":"x"}',
            '{"name":false,"url":"/a"}',
            "x" * 9000,
        ):
            with patch("sys.stdin", io.StringIO(value)), self.assertRaises(CliError):
                _request(
                    _parser().parse_args(["links", "add", "--stdin", "--confirm"]), self
                )
        with self.assertRaisesRegex(CliError, "confirmation_required"):
            _request(
                _parser().parse_args(["links", "add", "--from", "rock-safe-person"]),
                self,
            )
        self.assertEqual(self.calls, [])

    def test_broker_rejects_preview_and_disabled_terminal_without_network(self):
        self.broker._context = Context.DEV
        result = self.broker.handle(
            {"op": "personal_link_prepare", "requestId": "test"}
        )
        self.assertEqual(result["personalLink"]["error"], "personal_links_preview_only")
        self.broker._context = Context.PROD
        self.broker._profile_store.update_preferences({"terminalAccess": False})
        result = self.broker.handle(
            {"op": "personal_link_prepare", "client": CLI_CLIENT}
        )
        self.assertEqual(result["error"], "terminal_access_disabled")
        self.assertEqual(self.rock.calls, [])

    def test_long_search_title_is_prefilled_without_splitting_unicode(self):
        self.live.target = NavigationTarget(
            "😀" * 60, "Person", 10, ORIGIN + "/Person/17"
        )
        result = self.request(
            {"op": "personal_link_prepare", "safeId": "rock-safe-person"}
        )
        self.assertEqual(result["personalLink"]["name"], "😀" * 50)
        self.assertEqual(self.rock.writes, [])

    def test_switching_profiles_on_same_origin_invalidates_draft(self):
        draft = self.request({"op": "personal_link_prepare"})["personalLink"]
        profile = self.broker._profile_store.add("Second account", ORIGIN)
        self.broker.handle({"op": "profile_switch", "profileId": profile.profile_id})
        result = self.broker.handle(
            {
                "op": "personal_link_save",
                **draft,
                "name": "Test",
                "url": "/page/42",
                "confirmed": True,
            }
        )
        self.assertEqual(result["error"], "personal_link_draft_expired")
        self.assertEqual(self.rock.writes, [])

    def test_sign_out_invalidates_an_open_draft(self):
        draft = self.broker.handle({"op": "personal_link_prepare"})["personalLink"]
        self.broker.handle({"op": "profile_sign_out"})
        self.assertFalse(self.manager._drafts)
        result = self.broker.handle(
            {
                "op": "personal_link_save",
                **draft,
                "name": "Page",
                "url": "/page/42",
                "confirmed": True,
            }
        )
        self.assertFalse(result["ok"])
        self.assertEqual(self.rock.writes, [])

    def test_authorization_denial_invalidates_cookie_without_retrying(self):
        with (
            patch.object(
                self.rock,
                "get",
                side_effect=PersonalLinkError("personal_links_not_authorized"),
            ) as get,
            patch.object(
                self.broker._session, "invalidate_authenticated_cookie"
            ) as invalidate,
        ):
            result = self.broker.handle(
                {"op": "personal_link_prepare", "requestId": "denied"}
            )
        self.assertFalse(result["ok"])
        self.assertEqual(
            result["personalLink"],
            {
                "requestId": "denied",
                "error": "personal_links_not_authorized",
            },
        )
        get.assert_called_once()
        invalidate.assert_called_once_with()
        self.assertEqual(self.rock.writes, [])

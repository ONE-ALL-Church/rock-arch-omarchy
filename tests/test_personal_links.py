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
        self.corrupt_readback = False

    @property
    def writes(self):
        return [call for call in self.calls if call[0] == "POST"]

    def get(self, origin, path, params, cookie):
        self.calls.append(("GET", path, copy.deepcopy(params)))
        if path == CURRENT_PERSON:
            return dict(self.person)
        if path == SECTIONS:
            return copy.deepcopy(self.sections)
        condition = params["$filter"]
        match = re.search(r"and Id eq (\d+)", condition)
        if match:
            rows = [dict(item) for item in self.links if item["Id"] == int(match[1])]
            if rows and self.corrupt_readback:
                rows[0]["SectionId"] = 999
            return rows
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
            self.sections.append(
                {
                    "Id": 9,
                    "Name": body["Name"],
                    "IsShared": body["IsShared"],
                    "PersonAliasId": body["PersonAliasId"],
                }
            )
            return 9
        self.links.append({"Id": 100 + len(self.links), **body})
        if self.lose_response:
            raise PersonalLinkError("personal_link_save_uncertain")
        return self.links[-1]["Id"]


class PersonalLinkTests(unittest.TestCase):
    def setUp(self):
        self.rock = FakeRock()
        self.manager = PersonalLinkManager(Cookie(), self.rock)
        self.manager.set_origin(ORIGIN)

    def draft(self):
        return self.manager.prepare("People", "/page/42")

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
        self.calls = []

    def request(self, payload):
        self.calls.append(dict(payload))
        result = self.broker.handle({**payload, "client": CLI_CLIENT})
        if not result["ok"]:
            raise CliError(result["error"])
        return result

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

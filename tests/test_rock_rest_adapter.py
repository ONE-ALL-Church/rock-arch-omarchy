import json
import threading
import unittest
import urllib.error
from contextlib import contextmanager

from rock_arch_broker.navigation import NavigationError, validate_rock_url
from rock_arch_broker.origin import DEFAULT_ROCK_ORIGIN
from rock_arch_broker.rock_rest_adapter import (
    MAX_RESPONSE_BYTES,
    SEARCH_SPECS,
    RockRestError,
    RockRestHttpClient,
    RockRestReadOnlyAdapter,
)
from rock_arch_broker.version import HTTP_USER_AGENT


class FakeCookieProvider:
    def __init__(self):
        self.invalidated = False

    @contextmanager
    def authenticated_cookie(self):
        yield ".ROCK=test-session"

    def invalidate_authenticated_cookie(self):
        self.invalidated = True


class FakeHttp:
    def __init__(self, responses=None, failures=()):
        self.responses = responses or {}
        self.failures = set(failures)
        self.calls = []

    def get_json(self, path, params, cookie):
        self.calls.append((path, params, cookie))
        if path in self.failures:
            raise RockRestError("rock_request_failed")
        return self.responses.get(path, [])


class CapabilityHttp(FakeHttp):
    def __init__(self, unavailable=(), transient=()):
        super().__init__()
        self.unavailable = set(unavailable)
        self.transient = set(transient)

    def get_json(self, path, params, cookie):
        self.calls.append((path, params, cookie))
        if path in self.unavailable:
            raise RockRestError("rock_endpoint_unavailable")
        if path in self.transient:
            raise RockRestError("rock_request_failed")
        return []


class ConcurrentHttp:
    def __init__(self):
        self.barrier = threading.Barrier(len(SEARCH_SPECS))

    def get_json(self, path, params, cookie):
        self.barrier.wait(timeout=2)
        return []


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, maximum):
        return self.payload[:maximum]


class FakeOpener:
    def __init__(self, payload=b"[]"):
        self.payload = payload
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        return FakeResponse(self.payload)


class FailingOpener:
    def __init__(self, status):
        self.status = status

    def open(self, request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, self.status, "request failed", {}, None
        )


class RockRestAdapterTests(unittest.TestCase):
    def test_http_client_is_get_only_exact_origin_and_forwards_cookie_in_header(self):
        opener = FakeOpener(b'[{"Id":1}]')
        client = RockRestHttpClient(opener, origin="https://rock.example.org")
        value = client.get_json(
            "/api/People",
            {"$select": "Id", "$top": "3"},
            ".ROCK=test-session",
        )
        self.assertEqual(value, [{"Id": 1}])
        request, timeout = opener.calls[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Cookie"), ".ROCK=test-session")
        self.assertEqual(request.get_header("User-agent"), HTTP_USER_AGENT)
        self.assertTrue(
            request.full_url.startswith("https://rock.example.org/api/People?")
        )
        self.assertEqual(timeout, 20)

    def test_http_client_rejects_generic_endpoints_and_oversized_responses(self):
        opener = FakeOpener()
        client = RockRestHttpClient(opener)
        for path in (
            "/api/People/1",
            "/api/Auth/Login",
            "https://attacker.example/api/People",
        ):
            with (
                self.subTest(path=path),
                self.assertRaisesRegex(RockRestError, "endpoint_not_allowed"),
            ):
                client.get_json(path, {}, ".ROCK=test-session")
        self.assertEqual(opener.calls, [])

        oversized = RockRestHttpClient(FakeOpener(b"x" * (MAX_RESPONSE_BYTES + 1)))
        with self.assertRaisesRegex(RockRestError, "out_of_bounds"):
            oversized.get_json("/api/People", {}, ".ROCK=test-session")

    def test_http_client_reports_deep_json_as_a_stable_failure(self):
        payload = b"[" * 100_000 + b"]" * 100_000
        client = RockRestHttpClient(FakeOpener(payload))
        with self.assertRaisesRegex(RockRestError, "invalid_rock_response"):
            client.get_json("/api/People", {}, ".ROCK=test-session")

    def test_http_client_distinguishes_denied_endpoints_from_transient_failures(self):
        for status, expected in (
            (401, "rock_endpoint_unavailable"),
            (403, "rock_endpoint_unavailable"),
            (404, "rock_endpoint_unavailable"),
            (500, "rock_request_failed"),
        ):
            with self.subTest(status=status), self.assertRaisesRegex(
                RockRestError, expected
            ):
                RockRestHttpClient(FailingOpener(status)).get_json(
                    "/api/People", {"$select": "Id"}, ".ROCK=test-session"
                )

    def test_search_uses_only_fixed_get_specs_and_opaque_results(self):
        http = FakeHttp(
            {
                "/api/People": [
                    {
                        "Id": 17,
                        "NickName": "D'Angelo",
                        "LastName": "Stone",
                        "Email": "must-not-cross",
                    }
                ],
                "/api/Groups": [
                    {
                        "Id": 4,
                        "Name": "Delta",
                        "IsActive": True,
                        "GroupType": {"Name": "Small Group"},
                    }
                ],
                "/api/GroupTypes": [
                    {"Id": 5, "Name": "Small Group"}
                ],
                "/api/WorkflowTypes": [
                    {"Id": 6, "Name": "Follow-up", "IsActive": True}
                ],
                "/api/ServiceJobs": [
                    {
                        "Id": 7,
                        "Name": "Data Sync",
                        "IsActive": True,
                        "LastStatus": "Success",
                    }
                ],
                "/api/Pages": [
                    {"Id": 9, "PageTitle": "Directory", "InternalName": "Dir"}
                ],
                "/api/ContentChannelTypes": [
                    {"Id": 11, "Name": "Blog"}
                ],
                "/api/ContentChannelItems": [
                    {"Id": 12, "Title": "Weekend Update", "Status": 1}
                ],
            }
        )
        adapter = RockRestReadOnlyAdapter(FakeCookieProvider(), http)
        batch = adapter.search("D'Angelo")

        self.assertEqual(
            {call[0] for call in http.calls}, {s.path for s in SEARCH_SPECS}
        )
        self.assertTrue(all(call[2] == ".ROCK=test-session" for call in http.calls))
        calls_by_path = {path: params for path, params, _ in http.calls}
        person_params = calls_by_path["/api/People"]
        self.assertIn("D''Angelo", person_params["$filter"])
        self.assertIn("startswith(NickName,'D''Angelo')", person_params["$filter"])
        self.assertIn("Age", person_params["$select"])
        self.assertIn("GivingGroupId", person_params["$select"])
        self.assertEqual(
            person_params["$expand"],
            "MaritalStatusValue,ConnectionStatusValue,RecordStatusValue",
        )
        self.assertEqual(person_params["$top"], "3")
        group_params = calls_by_path["/api/Groups"]
        self.assertEqual(group_params["$expand"], "GroupType")
        self.assertIn("GroupType/Name", group_params["$select"])
        person = batch.results[0]
        self.assertTrue(person["safeId"].startswith("rock-"))
        self.assertEqual(len(person["safeId"]), 37)
        self.assertNotEqual(person["safeId"], "17")
        self.assertTrue(person["canOpen"])
        self.assertNotIn("Email", person)
        self.assertNotIn("must-not-cross", json.dumps(batch.results))
        page = next(row for row in batch.results if row["category"] == "Pages")
        self.assertEqual(page["title"], "Directory")
        group = next(row for row in batch.results if row["category"] == "Groups")
        self.assertEqual(group["subtitle"], "Small Group")
        self.assertTrue(all(row["canOpen"] for row in batch.results))

        expected_targets = {
            "People": ("Person", "/Person/17"),
            "Groups": ("Group", "/Group/4"),
            "Group Types": (
                "Group Type",
                "/admin/general/group-types?GroupTypeId=5",
            ),
            "Workflows": (
                "Workflow Type",
                "/admin/general/workflows?WorkflowTypeId=6",
            ),
            "Jobs": ("Scheduled Job", "/admin/system/jobs/7"),
            "Pages": ("Page", "/page/9"),
            "Content Channel Types": (
                "Content Channel Type",
                "/admin/cms/content-channel-type?ContentChannelTypeId=11",
            ),
            "Content Channel Items": (
                "Content Channel Item",
                "/ContentChannelItem/12",
            ),
        }
        for result in batch.results:
            with self.subTest(category=result["category"]):
                target = adapter.resolve(result["safeId"])
                self.assertIsNotNone(target)
                assert target is not None
                expected_kind, expected_path = expected_targets[result["category"]]
                self.assertEqual(target.kind, expected_kind)
                self.assertEqual(target.url, DEFAULT_ROCK_ORIGIN + expected_path)

        quick_look = adapter.person_quick_look(person["safeId"])
        self.assertIsNotNone(quick_look)
        assert quick_look is not None
        self.assertEqual(quick_look["campus"], "Campus not available")
        target = adapter.resolve(person["safeId"])
        self.assertIsNotNone(target)
        assert target is not None
        self.assertEqual(
            target.url,
            "https://rock.example.org/Person/17",
        )

    def test_people_include_bounded_duplicate_name_context(self):
        http = FakeHttp(
            {
                "/api/People": [
                    {
                        "Id": 17,
                        "NickName": "Jamie",
                        "LastName": "Stone",
                        "Age": 33,
                        "GivingGroupId": 91,
                        "MaritalStatusValue": {"Value": "Married"},
                        "ConnectionStatusValue": {"Value": "Member"},
                        "RecordStatusValue": {"Value": "Active"},
                        "Email": "must-not-cross",
                    }
                ],
                "/api/Groups": [
                    {
                        "Id": 91,
                        "Campus": {"Name": "North Campus"},
                        "Members": [
                            {
                                "PersonId": 17,
                                "IsArchived": False,
                                "GroupRole": {"Name": "Adult"},
                                "Person": {
                                    "NickName": "Jamie",
                                    "LastName": "Stone",
                                },
                            },
                            {
                                "PersonId": 18,
                                "IsArchived": False,
                                "GroupRole": {"Name": "Adult"},
                                "Person": {
                                    "NickName": "Alex",
                                    "LastName": "Stone",
                                    "Email": "also-must-not-cross",
                                },
                            },
                            {
                                "PersonId": 19,
                                "IsArchived": False,
                                "GroupRole": {"Name": "Child"},
                                "Person": {
                                    "NickName": "Casey",
                                    "LastName": "Stone",
                                },
                            },
                        ],
                    }
                ],
            }
        )
        adapter = RockRestReadOnlyAdapter(FakeCookieProvider(), http)
        batch = adapter.search("Jamie", "People")

        self.assertEqual(
            [call[0] for call in http.calls], ["/api/People", "/api/Groups"]
        )
        family_params = http.calls[1][1]
        self.assertEqual(family_params["$filter"], "Id eq 91")
        self.assertIn("Campus/Name", family_params["$select"])
        self.assertIn("Members/GroupRole/Name", family_params["$select"])
        self.assertEqual(len(batch.results), 1)
        person = batch.results[0]
        self.assertEqual(
            person["subtitle"], "Age 33 · Spouse Alex Stone · North Campus"
        )
        self.assertEqual(person["status"], "Member")
        self.assertNotIn("must-not-cross", json.dumps(batch.results))

        quick_look = adapter.person_quick_look(person["safeId"])
        self.assertIsNotNone(quick_look)
        assert quick_look is not None
        self.assertEqual(quick_look["subtitle"], "Age 33 · Spouse Alex Stone · Member")
        self.assertEqual(quick_look["campus"], "Campus · North Campus")
        self.assertNotIn("must-not-cross", json.dumps(quick_look))

        adapter.search("Jamie", "People")
        self.assertEqual(
            sum(path == "/api/Groups" for path, _, _ in http.calls),
            1,
        )

        http.responses["/api/Groups"][0]["Members"].append(
            {
                "PersonId": 20,
                "IsArchived": False,
                "GroupRole": {"Name": "Adult"},
                "Person": {"NickName": "Morgan", "LastName": "Stone"},
            }
        )
        adapter.clear()
        ambiguous = adapter.search("Jamie", "People").results[0]
        self.assertNotIn("Spouse", ambiguous["subtitle"])

    def test_person_context_can_be_disabled_before_the_request(self):
        http = FakeHttp(
            {
                "/api/People": [
                    {
                        "Id": 17,
                        "NickName": "Jamie",
                        "LastName": "Stone",
                        "Age": 33,
                        "GivingGroupId": 91,
                    }
                ]
            }
        )
        batch = RockRestReadOnlyAdapter(FakeCookieProvider(), http).search(
            "Jamie", "People", include_person_context=False
        )
        self.assertEqual([call[0] for call in http.calls], ["/api/People"])
        self.assertEqual(http.calls[0][1]["$select"], "Id,NickName,LastName")
        self.assertNotIn("$expand", http.calls[0][1])
        self.assertEqual(batch.results[0]["subtitle"], "Person")
        self.assertNotIn("Age", json.dumps(batch.results))

    def test_search_returns_partial_results_without_falling_back(self):
        failed = {"/api/Groups", "/api/ServiceJobs"}
        http = FakeHttp({"/api/People": []}, failures=failed)
        adapter = RockRestReadOnlyAdapter(FakeCookieProvider(), http)
        batch = adapter.search("Ada")
        self.assertEqual(batch.results, [])
        self.assertEqual(batch.unavailable, ("Groups", "Jobs"))

    def test_search_starts_all_fixed_category_reads_concurrently(self):
        batch = RockRestReadOnlyAdapter(FakeCookieProvider(), ConcurrentHttp()).search(
            "Ada"
        )
        self.assertEqual(batch.results, [])
        self.assertEqual(batch.unavailable, ())

    def test_searchable_categories_are_probed_once_and_cached(self):
        http = CapabilityHttp(
            unavailable={"/api/WorkflowTypes", "/api/ServiceJobs"}
        )
        adapter = RockRestReadOnlyAdapter(FakeCookieProvider(), http)

        first = adapter.searchable_categories()
        second = adapter.searchable_categories()

        self.assertEqual(first, second)
        self.assertEqual(first.unavailable, ("Workflows", "Jobs"))
        self.assertNotIn("Workflows", first.available)
        self.assertNotIn("Jobs", first.available)
        self.assertEqual(len(http.calls), len(SEARCH_SPECS))
        self.assertTrue(
            all(params == {"$select": "Id", "$top": "1"} for _, params, _ in http.calls)
        )

        adapter.clear()
        adapter.searchable_categories()
        self.assertEqual(len(http.calls), len(SEARCH_SPECS) * 2)

    def test_searchable_categories_fail_closed_on_transient_errors(self):
        adapter = RockRestReadOnlyAdapter(
            FakeCookieProvider(), CapabilityHttp(transient={"/api/People"})
        )
        with self.assertRaisesRegex(RockRestError, "capability_check_failed"):
            adapter.searchable_categories()

    def test_scoped_search_calls_only_one_endpoint_and_allows_an_empty_term(self):
        http = FakeHttp(
            {
                "/api/Groups": [
                    {
                        "Id": 4,
                        "Name": "Delta",
                        "IsActive": True,
                        "GroupType": {"Name": "Small Group"},
                    }
                ]
            }
        )
        batch = RockRestReadOnlyAdapter(FakeCookieProvider(), http).search("", "Groups")
        self.assertEqual([call[0] for call in http.calls], ["/api/Groups"])
        self.assertNotIn("$filter", http.calls[0][1])
        self.assertEqual(batch.results[0]["subtitle"], "Small Group")
        self.assertEqual(batch.unavailable, ())

    def test_text_search_matches_terms_anywhere_in_entity_names(self):
        http = FakeHttp({"/api/WorkflowTypes": []})

        RockRestReadOnlyAdapter(FakeCookieProvider(), http).search(
            "Approval", "Workflows"
        )

        self.assertEqual(
            http.calls[0][1]["$filter"],
            "substringof('Approval',Name)",
        )

        http.calls.clear()
        RockRestReadOnlyAdapter(FakeCookieProvider(), http).search(
            "Approval", "Groups"
        )
        self.assertEqual(
            http.calls[0][1]["$filter"],
            "startswith(Name,'Approval')",
        )

    def test_scoped_ids_and_guids_use_exact_identity_filters(self):
        http = FakeHttp({"/api/Groups": []})
        adapter = RockRestReadOnlyAdapter(FakeCookieProvider(), http)

        adapter.search("004", "Groups")
        self.assertEqual(http.calls[-1][1]["$filter"], "Id eq 4")

        guid = "A81B7C6D-1234-4ABC-9876-0123456789AB"
        adapter.search(guid, "Groups")
        self.assertEqual(
            http.calls[-1][1]["$filter"],
            "Guid eq guid'a81b7c6d-1234-4abc-9876-0123456789ab'",
        )

    def test_unscoped_ids_and_guids_search_all_enabled_entities(self):
        http = FakeHttp()
        adapter = RockRestReadOnlyAdapter(FakeCookieProvider(), http)
        guid = "a81b7c6d-1234-4abc-9876-0123456789ab"

        adapter.search(guid)
        self.assertEqual(len(http.calls), len(SEARCH_SPECS))
        self.assertTrue(
            all(
                params["$filter"] == f"Guid eq guid'{guid}'"
                for _, params, _ in http.calls
            )
        )

        http.calls.clear()
        adapter.search("17")
        self.assertTrue(
            all(params["$filter"] == "Id eq 17" for _, params, _ in http.calls)
        )

    def test_scoped_search_rejects_unknown_internal_categories(self):
        with self.assertRaisesRegex(RockRestError, "invalid_search_scope"):
            RockRestReadOnlyAdapter(FakeCookieProvider(), FakeHttp()).search(
                "Ada", "Unknown"
            )

    def test_personal_links_are_same_origin_and_never_expose_urls(self):
        http = FakeHttp(
            {
                "/api/PersonalLinks/GetPersonalLinksData": {
                    "PersonLinksSectionList": [
                        {
                            "Name": "My tools",
                            "Order": 2,
                            "IsShared": False,
                            "PersonalLinks": [
                                {"Name": "People", "Url": "/page/12", "Order": 1},
                                {
                                    "Name": "External",
                                    "Url": "https://attacker.example/",
                                    "Order": 2,
                                },
                            ],
                        }
                    ]
                }
            }
        )
        adapter = RockRestReadOnlyAdapter(FakeCookieProvider(), http)
        links = adapter.personal_links()
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["title"], "People")
        self.assertEqual(links[0]["section"], "My tools")
        self.assertNotIn("url", json.dumps(links).lower())
        target = adapter.resolve(links[0]["safeId"])
        self.assertIsNotNone(target)
        assert target is not None
        self.assertEqual(target.url, "https://rock.example.org/page/12")

        cached = adapter.personal_links()
        self.assertEqual(cached, links)
        self.assertEqual(len(http.calls), 1)

        refreshed = adapter.personal_links(force_refresh=True)
        self.assertEqual(refreshed, links)
        self.assertEqual(len(http.calls), 2)

    def test_all_category_failures_are_stable(self):
        http = FakeHttp(failures={spec.path for spec in SEARCH_SPECS})
        cookie_provider = FakeCookieProvider()
        with self.assertRaisesRegex(RockRestError, "rock_search_failed"):
            RockRestReadOnlyAdapter(cookie_provider, http).search("Ada")
        self.assertTrue(cookie_provider.invalidated)

    def test_url_validation_is_exact_origin_https(self):
        self.assertEqual(
            validate_rock_url("/Person/7", DEFAULT_ROCK_ORIGIN),
            "https://rock.example.org/Person/7",
        )
        for value in (
            "http://rock.example.org/Person/7",
            "https://attacker.example/",
            "//attacker.example/path",
            "https://rock.example.org.attacker.example/",
        ):
            with self.subTest(value=value), self.assertRaises(NavigationError):
                validate_rock_url(value, DEFAULT_ROCK_ORIGIN)


if __name__ == "__main__":
    unittest.main()

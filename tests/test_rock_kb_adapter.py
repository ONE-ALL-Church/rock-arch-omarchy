import json
import unittest
import urllib.error

from rock_lens_broker.contracts import ALLOWED_RESULT_KEYS
from rock_lens_broker.rock_kb_adapter import (
    DETAIL_RESPONSE_LIMIT,
    HTTP_TIMEOUT_SECONDS,
    ROCK_KB_ORIGIN,
    SEARCH_RESPONSE_LIMIT,
    RockKbError,
    RockKbHttpClient,
    RockKbReadOnlyAdapter,
    parse_knowledge_query,
    validate_public_source_url,
)
from rock_lens_broker.version import HTTP_USER_AGENT


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
    def __init__(self, payload=b'{"schema":"rock-kb-search-result-v3","results":[]}'):
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


class FakeHttp:
    def __init__(self):
        self.search_calls = []
        self.result_calls = []
        self.body = "Check the printer route.\n\nThen run a test check-in."

    def search(self, query, limit=10):
        self.search_calls.append((query, limit))
        return {
            "schema": "rock-kb-search-result-v3",
            "results": [
                {
                    "id": "task_card:check-in:labels",
                    "kind": "task_card",
                    "title": "Diagnose labels",
                    "snippet": "Check the printer route before changing the label.",
                    "url": "https://github.com/SparkDevNetwork/Rock/blob/develop/example.cs",
                    "authority_tier": "community-reviewed",
                    "claim_tier": "source_backed",
                    "private": "must-not-cross",
                }
            ],
        }

    def result(self, result_id):
        self.result_calls.append(result_id)
        return {
            "schema": "rock-kb-result-v1",
            "status": "ok",
            "requested_result_id": result_id,
            "canonical_result_id": result_id,
            "result": {
                "id": result_id,
                "kind": "task_card",
                "title": "Diagnose labels",
                "body": self.body,
                "url": "",
                "authority_tier": "community-reviewed",
                "claim_tier": "source_backed",
                "rock_versions": ["19.0"],
                "version_scope_status": "matched",
                "payload": {
                    "source_urls": [
                        "https://github.com/SparkDevNetwork/Rock/blob/develop/example.cs"
                    ],
                    "secret": "must-not-cross",
                },
            },
        }


class ScopedFakeHttp(FakeHttp):
    def __init__(self):
        super().__init__()
        self.model_calls = []
        self.lava_calls = []
        self.concept_calls = []
        self.issue_calls = []
        self.idea_calls = []

    def models(self):
        return {
            "schema": "rock-kb-model-map-model-list-v1",
            "models": [
                {
                    "model_name": "Group",
                    "model_title": "Group",
                    "model_slug": "group",
                    "model_category": "Groups",
                    "property_count": 115,
                    "method_count": 55,
                    "rock_version": "19.2.0",
                },
                {
                    "model_name": "Group Member",
                    "model_title": "GroupMember",
                    "model_slug": "group-member",
                    "model_category": "Groups",
                    "property_count": 48,
                    "method_count": 20,
                    "rock_version": "19.2.0",
                },
            ],
        }

    def model(self, model_slug):
        self.model_calls.append(model_slug)
        return {
            "matched_model": {"model_slug": model_slug},
            "model": {
                "identity": {
                    "model_slug": model_slug,
                    "model_name": "Group" if model_slug == "group" else "Group Member",
                    "model_category": "Groups",
                    "rock_version": "19.2.0",
                },
                "counts": {
                    "properties": 115,
                    "database_properties": 61,
                    "lava_properties": 93,
                    "relationships": 1,
                    "methods": 55,
                },
                "required_fields": [{"name": "Name"}],
                "relationships": [
                    {
                        "property_name": "GroupMembers",
                        "related_model": "Group Member",
                        "target_model_slug": "group-member",
                    }
                ] if model_slug == "group" else [],
            },
        }

    def lava_contexts(self):
        return {
            "schema": "rock-kb-lava-context-surface-list-v1",
            "surfaces": [
                {
                    "context_id": "workflow-activate",
                    "surface_name": "Workflow activation",
                    "context_family": "workflow",
                    "surface_type": "workflow_action",
                    "direct_root_count": 1,
                    "root_keys": ["Workflow"],
                    "source_version": "19.2.0",
                }
            ],
        }

    def lava_context(self, context_id):
        self.lava_calls.append(context_id)
        return {
            "schema": "rock-kb-lava-context-surface-result-v2",
            "status": "ok",
            "surface": {
                "context_id": context_id,
                "surface_name": "Workflow activation",
                "context_family": "workflow",
                "surface_type": "workflow_action",
                "source_version": "19.2.0",
                "concept_ids": ["workflows"],
            },
            "roots": [
                {
                    "root_key": "Workflow",
                    "model_slug": "workflow",
                    "source_url": "https://github.com/SparkDevNetwork/Rock/blob/develop/Workflow.cs",
                }
            ],
        }

    def concepts(self):
        return {"rows": [{"concept_id": "groups", "title": "Groups", "source_count": 42}]}

    def concept(self, concept_id):
        self.concept_calls.append(concept_id)
        return "# Groups\n\nHow Rock groups are structured."

    def issue_search(self, query, limit=10):
        self.issue_calls.append((query, limit))
        return {
            "schema": "rock-kb-rock-issue-search-v1",
            "results": [{
                "id": "rock_issue:core:123",
                "kind": "rock_issue",
                "title": "Labels do not print",
                "snippet": "A community-reported check-in issue.",
                "authority_tier": "community-unreviewed",
                "claim_tier": "routing_context_only",
                "url": "https://github.com/SparkDevNetwork/Rock/issues/123",
            }],
        }

    def idea_search(self, query, limit=10):
        self.idea_calls.append((query, limit))
        return {"schema": "rock-kb-rock-idea-search-v1", "results": []}

    def result(self, result_id):
        self.result_calls.append(result_id)
        return {
            "schema": "rock-kb-result-v1",
            "status": "ok",
            "requested_result_id": result_id,
            "canonical_result_id": result_id,
            "result": {
                "id": result_id,
                "kind": "task_card",
                "title": "Diagnose labels",
                "body": self.body,
                "url": "",
                "authority_tier": "community-reviewed",
                "claim_tier": "source_backed",
                "rock_versions": ["19.0"],
                "version_scope_status": "matched",
                "payload": {
                    "source_urls": [
                        "https://github.com/SparkDevNetwork/Rock/blob/develop/example.cs"
                    ],
                    "secret": "must-not-cross",
                },
            },
        }


class RockKbAdapterTests(unittest.TestCase):
    def test_local_knowledge_area_prefixes_do_not_change_generic_queries(self):
        self.assertEqual(parse_knowledge_query("mm: Group"), ("model", "Group"))
        self.assertEqual(parse_knowledge_query("is: labels"), ("issue", "labels"))
        self.assertEqual(parse_knowledge_query("lava: workflow"), ("lava", "workflow"))
        self.assertEqual(parse_knowledge_query("how do groups work"), ("all", "how do groups work"))

    def test_http_client_is_fixed_origin_get_only_and_sends_no_rock_credentials(self):
        opener = FakeOpener()
        client = RockKbHttpClient(opener)

        value = client.search("Rock API authentication")

        self.assertEqual(value["results"], [])
        request, timeout = opener.calls[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertTrue(request.full_url.startswith(ROCK_KB_ORIGIN + "/search?"))
        self.assertIn("min_claim_tier=source_backed", request.full_url)
        self.assertIn("detail=compact", request.full_url)
        self.assertEqual(request.get_header("User-agent"), HTTP_USER_AGENT)
        self.assertIsNone(request.get_header("Cookie"))
        self.assertIsNone(request.get_header("Authorization"))
        self.assertEqual(timeout, HTTP_TIMEOUT_SECONDS)

    def test_http_client_bounds_queries_results_and_responses(self):
        client = RockKbHttpClient(FakeOpener())
        for query in ("", "a", "ab"):
            with self.subTest(query=query), self.assertRaisesRegex(
                RockKbError, "invalid_knowledge_query"
            ):
                client.search(query)

        with self.assertRaisesRegex(RockKbError, "out_of_bounds"):
            RockKbHttpClient(
                FakeOpener(b"x" * (SEARCH_RESPONSE_LIMIT + 1))
            ).search("valid query")
        detail_client = RockKbHttpClient(
            FakeOpener(b"x" * (DETAIL_RESPONSE_LIMIT + 1))
        )
        with self.assertRaisesRegex(RockKbError, "out_of_bounds"):
            detail_client.result("claim:test")

    def test_http_client_maps_not_found_and_service_failures_to_stable_errors(self):
        with self.assertRaisesRegex(RockKbError, "result_not_found"):
            RockKbHttpClient(FailingOpener(404)).result("claim:test")
        with self.assertRaisesRegex(RockKbError, "knowledge_unavailable"):
            RockKbHttpClient(FailingOpener(500)).search("valid query")

    def test_search_and_detail_expose_only_opaque_bounded_public_fields(self):
        http = FakeHttp()
        adapter = RockKbReadOnlyAdapter(http)

        results = adapter.search("labels not printing")

        self.assertEqual(len(results), 1)
        self.assertLessEqual(set(results[0]), ALLOWED_RESULT_KEYS)
        self.assertEqual(results[0]["category"], "Knowledge")
        self.assertEqual(results[0]["status"], "Community reviewed")
        self.assertRegex(results[0]["safeId"], r"^kb-[0-9a-f]{32}$")
        serialized = json.dumps(results[0])
        self.assertNotIn("task_card:check-in:labels", serialized)
        self.assertNotIn("github.com", serialized)
        self.assertNotIn("must-not-cross", serialized)

        detail = adapter.detail(results[0]["safeId"])

        self.assertEqual(detail["kind"], "Task card")
        self.assertEqual(detail["trust"], "Community reviewed")
        self.assertEqual(detail["claimTier"], "Source backed")
        self.assertEqual(detail["version"], "Rock 19.0")
        self.assertEqual(detail["sourceHost"], "github.com")
        self.assertTrue(detail["canOpenSource"])
        self.assertNotIn("url", {key.lower() for key in detail})
        self.assertNotIn("must-not-cross", json.dumps(detail))
        self.assertEqual(
            adapter.source_url(results[0]["safeId"]),
            "https://github.com/SparkDevNetwork/Rock/blob/develop/example.cs",
        )

    def test_detail_removes_a_repeated_leading_title(self):
        http = FakeHttp()
        http.body = "# Diagnose labels\n\nCheck the printer route."
        adapter = RockKbReadOnlyAdapter(http)

        safe_id = adapter.search("label printing")[0]["safeId"]

        self.assertEqual(
            adapter.detail(safe_id)["body"], "Check the printer route."
        )

    def test_search_and_detail_are_cached_without_repeating_network_calls(self):
        http = FakeHttp()
        adapter = RockKbReadOnlyAdapter(http)

        first = adapter.search("labels not printing")
        second = adapter.search("Labels Not Printing")
        adapter.detail(first[0]["safeId"])
        adapter.detail(second[0]["safeId"])

        self.assertEqual(len(http.search_calls), 1)
        self.assertEqual(len(http.result_calls), 1)

    def test_public_source_validation_rejects_local_credentials_and_non_https(self):
        self.assertEqual(
            validate_public_source_url("https://community.rockrms.com/docs?q=1"),
            "https://community.rockrms.com/docs?q=1",
        )
        for value in (
            "http://community.rockrms.com/docs",
            "https://user:pass@community.rockrms.com/docs",
            "https://localhost/docs",
            "https://127.0.0.1/docs",
            "https://community.rockrms.com:8443/docs",
            "file:///tmp/private",
            "https://community.rockrms.com\\@attacker.example/",
        ):
            with self.subTest(value=value), self.assertRaisesRegex(
                RockKbError, "invalid_knowledge_source"
            ):
                validate_public_source_url(value)

    def test_model_map_results_open_and_expose_only_opaque_related_models(self):
        http = ScopedFakeHttp()
        adapter = RockKbReadOnlyAdapter(http)

        result = adapter.search("mm: group")[0]
        detail = adapter.detail(result["safeId"])

        self.assertEqual(result["status"], "Rock 19.2.0")
        self.assertEqual(detail["kind"], "Model Map")
        self.assertIn("Required fields\nName", detail["body"])
        self.assertEqual(detail["links"][0]["title"], "Group Member")
        self.assertNotIn("group-member", json.dumps(detail["links"]))

        related = adapter.detail(detail["links"][0]["safeId"])
        self.assertEqual(related["title"], "Group Member")
        self.assertEqual(http.model_calls, ["group", "group-member"])

    def test_lava_concept_and_issue_areas_use_their_bounded_routes(self):
        http = ScopedFakeHttp()
        adapter = RockKbReadOnlyAdapter(http)

        lava = adapter.detail(adapter.search("lava: workflow")[0]["safeId"])
        concept = adapter.detail(adapter.search("guide: groups")[0]["safeId"])
        issue = adapter.search("is: labels")[0]

        self.assertEqual(lava["links"][0]["kind"], "Model Map")
        self.assertEqual(concept["body"], "How Rock groups are structured.")
        self.assertEqual(issue["status"], "Community report · unreviewed")
        self.assertEqual(http.lava_calls, ["workflow-activate"])
        self.assertEqual(http.concept_calls, ["groups"])
        self.assertEqual(http.issue_calls, [("labels", 10)])


if __name__ == "__main__":
    unittest.main()

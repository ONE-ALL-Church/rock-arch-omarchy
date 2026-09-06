import unittest

from rock_arch_broker.rock_kb_adapter import RockKbReadOnlyAdapter

CODE = "https://github.com/SparkDevNetwork/Rock/blob/develop/Rock/Model/Group.cs"
ARTICLE = "https://community.rockrms.com/connect/example-article"
VIDEO = "https://www.youtube.com/watch?v=example&t=203s"
ISSUE = "https://github.com/SparkDevNetwork/Rock/issues/123"
ARTIFACT = "https://github.com/ONE-ALL-Church/rock-agent-kb/blob/main/knowledge/example.md"


class SourceHttp:
    def __init__(self, url=CODE, payload=None, search_url=CODE):
        self.url = url
        self.payload = payload or {}
        self.search_url = search_url
        self.detail_calls = 0

    def search(self, query, limit):
        return {"schema": "rock-kb-search-result-v3", "results": [{
            "id": "claim:source-example", "kind": "claim", "title": "A public reference",
            "url": self.search_url,
        }]}

    def result(self, result_id):
        self.detail_calls += 1
        return {
            "schema": "rock-kb-result-v1", "status": "ok",
            "requested_result_id": result_id, "canonical_result_id": result_id,
            "result": {
                "id": result_id, "kind": "claim", "title": "A public reference",
                "body": "An example URL in body text is not a source: https://example.com/unrelated",
                "url": self.url, "payload": self.payload,
            },
        }


class KnowledgeSourceTests(unittest.TestCase):
    def test_original_article_video_and_issue_win_over_code_and_kb_artifacts(self):
        for original in (ARTICLE, VIDEO, ISSUE):
            for primary in (CODE, ARTIFACT):
                with self.subTest(original=original, primary=primary):
                    adapter = RockKbReadOnlyAdapter(SourceHttp(primary, {"source_urls": [CODE, original]}))
                    safe_id = adapter.search("example")[0]["safeId"]
                    detail = adapter.detail(safe_id)
                    self.assertEqual(adapter.source_url(safe_id), original)
                    self.assertEqual(detail["sourceHost"], original.split('/')[2])
                    self.assertTrue(detail["canOpenSource"])

    def test_citation_shapes_supply_original_sources_and_preserve_video_timestamp(self):
        for payload in (
            {"source_url": VIDEO},
            {"citations": [{"url": "https://www.youtube.com/watch?v=example", "source_timestamp_url": VIDEO}]},
            {"source_refs": [{"url": VIDEO}]},
            {"approved_claims": [{"source_refs": [{"url": VIDEO}]}]},
        ):
            with self.subTest(payload=payload):
                adapter = RockKbReadOnlyAdapter(SourceHttp("", payload, search_url=""))
                safe_id = adapter.search("example")[0]["safeId"]
                self.assertEqual(adapter.source_url(safe_id), VIDEO)
                self.assertTrue(adapter.detail(safe_id)["canOpenSource"])

    def test_cli_can_resolve_original_source_before_the_reader_is_opened(self):
        http = SourceHttp(CODE, {"citations": [{"url": ARTICLE}]})
        adapter = RockKbReadOnlyAdapter(http)
        safe_id = adapter.search("example")[0]["safeId"]
        self.assertEqual(adapter.source_url(safe_id), ARTICLE)
        self.assertEqual(http.detail_calls, 1)

    def test_search_refresh_does_not_replace_resolved_article_with_code(self):
        http = SourceHttp(CODE, {"citations": [{"url": ARTICLE}]})
        adapter = RockKbReadOnlyAdapter(http)
        safe_id = adapter.search("example")[0]["safeId"]
        adapter.detail(safe_id)
        adapter.search("another query")
        self.assertEqual(adapter.source_url(safe_id), ARTICLE)
        self.assertEqual(http.detail_calls, 1)

    def test_primary_original_source_keeps_priority_over_other_readable_sources(self):
        for primary in (ARTICLE, VIDEO, ISSUE, "https://github.com/ONE-ALL-Church/rock-agent-kb/issues/3"):
            adapter = RockKbReadOnlyAdapter(SourceHttp(primary, {"source_urls": [ARTICLE, VIDEO, ISSUE]}))
            safe_id = adapter.search("example")[0]["safeId"]
            adapter.detail(safe_id)
            self.assertEqual(adapter.source_url(safe_id), primary)

    def test_search_metadata_is_preserved_when_detail_has_only_a_code_reference(self):
        adapter = RockKbReadOnlyAdapter(SourceHttp(CODE, search_url=ARTICLE))
        safe_id = adapter.search("example")[0]["safeId"]
        adapter.detail(safe_id)
        self.assertEqual(adapter.source_url(safe_id), ARTICLE)

    def test_code_is_retained_when_no_original_page_is_cited(self):
        adapter = RockKbReadOnlyAdapter(SourceHttp(CODE, {
            "related_issue_ids": [ISSUE],
            "example": {"url": ARTICLE},
            "distillations": [{"source_refs": [{"url": VIDEO}]}],
        }))
        self.assertEqual(adapter.source_url(adapter.search("example")[0]["safeId"]), CODE)

    def test_invalid_and_unbounded_citations_are_not_used(self):
        adapter = RockKbReadOnlyAdapter(SourceHttp(CODE, {
            "citations": [None, {"url": "http://example.com/"},
                          {"url": "https://localhost/"}, {"url": "https://user:password@example.com/"}]
                          + [{}] * 46 + [{"url": ARTICLE}],
            "source_refs": "https://example.com/",
            "source_urls": [None, {"url": ARTICLE}, "file:///etc/passwd"],
        }))
        self.assertEqual(adapter.source_url(adapter.search("example")[0]["safeId"]), CODE)

    def test_arbitrary_body_links_do_not_create_an_open_source_action(self):
        adapter = RockKbReadOnlyAdapter(SourceHttp("", search_url=""))
        safe_id = adapter.search("example")[0]["safeId"]
        self.assertIsNone(adapter.source_url(safe_id))
        self.assertFalse(adapter.detail(safe_id)["canOpenSource"])

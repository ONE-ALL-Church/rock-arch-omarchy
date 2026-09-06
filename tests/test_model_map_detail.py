import json
import unittest

from rock_arch_broker.model_map_detail import (
    MAX_MODEL_ROWS,
    MAX_MODEL_TEXT,
    model_sections,
)


class ModelMapDetailTests(unittest.TestCase):
    def test_overlapping_groups_render_once_with_descriptions_and_flags(self):
        row = {
            "name": "Status", "description": "Group status.\x00", "secret": "not-forwarded",
            "flags": {"required": True, "database": True, "lava": True, "obsolete": True},
            "obsolete_message": "Use State instead.",
            "enum_values": [{"value": "0", "label": "Active"}],
            "related_entities": [{"text": "Group", "entity_type_guid": "not-forwarded"}],
        }
        sections = model_sections({"property_groups": {"database": [row], "required": [row], "lava": [row]}})
        self.assertEqual(len(sections[0]["rows"]), 1)
        public = sections[0]["rows"][0]
        self.assertEqual(public["subtitle"], "Required · Database · Lava · Obsolete")
        for text in ("Group status.", "0 · Active", "Related: Group", "Use State instead."):
            self.assertIn(text, public["body"])
        self.assertNotIn("not-forwarded", json.dumps(sections))
        self.assertNotIn("\x00", public["body"])

    def test_methods_keep_distinct_overloads_and_sort_by_signature(self):
        sections = model_sections({"methods": [
            {"signature": "Z()"}, {"signature": "A(Person person)", "is_obsolete": True,
                "obsolete_message": "Use A()", "description": "Checks a person."},
            {"signature": "A()", "inherited": True},
        ]})
        rows = sections[1]["rows"]
        self.assertEqual([row["title"] for row in rows], ["A()", "A(Person person)", "Z()"])
        self.assertEqual(rows[0]["subtitle"], "Inherited")
        self.assertIn("Obsolete: Use A()", rows[1]["body"])

    def test_incomplete_snapshot_is_not_reported_as_complete(self):
        sections = model_sections({"counts": {"properties": 8, "methods": 0}})
        self.assertIn("Showing 0 of 8", sections[0]["notice"])
        self.assertIn("None documented", sections[1]["notice"])

    def test_untrusted_collections_and_values_are_not_stringified(self):
        sections = model_sections({"property_groups": {"database": [None, {"name": {}}, {
            "name": "Name", "description": {"token": "not-forwarded"}, "flags": ["required"]
        }]}, "methods": "invalid"})
        self.assertEqual(sections[0]["rows"], [{"title": "Name", "subtitle": "", "body": ""}])
        self.assertNotIn("not-forwarded", json.dumps(sections))

    def test_large_model_is_bounded_and_reports_omissions(self):
        rows = [{"name": f"Property{i:04}", "description": "x" * 5_000} for i in range(1_000)]
        sections = model_sections({"property_groups": {"database": rows}, "counts": {"properties": 1_000}})
        self.assertLessEqual(len(sections[0]["rows"]), MAX_MODEL_ROWS)
        size = sum(len(value) for section in sections for row in section["rows"] for value in row.values())
        self.assertLessEqual(size, MAX_MODEL_TEXT)
        self.assertIn("of 1000", sections[0]["notice"])

    def test_reference_defined_values_are_labeled_as_source_snapshot(self):
        sections = model_sections({"property_groups": {"defined_value": [{
            "name": "SourceValueId", "flags": {"defined_value": True},
            "enum_values": [{"value": "12 = Example", "label": "An example source"}],
        }]}})
        self.assertIn("Reference values (source snapshot)", sections[0]["rows"][0]["body"])

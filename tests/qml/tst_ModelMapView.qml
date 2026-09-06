import QtQuick
import QtTest
import "../../plugin/oneall.rock-arch" as RockArch

TestCase {
  name: "ModelMapView"
  RockArch.RockArchModelMapView { id: view }
  function init() {
    view.detail = {safeId: "kb-first", modelSections: [
      {key: "properties", title: "Properties", total: 2, rows: [
        {title: "Name", subtitle: "Required · Database", body: "The group name."},
        {title: "Members", subtitle: "Lava", body: "People belonging to the group."}
      ]},
      {key: "methods", title: "Methods", total: 1, rows: [
        {title: "GetMembers()", subtitle: "Inherited", body: "Returns people."}
      ]}
    ]}
  }
  function test_filter_matches_names_flags_and_descriptions_without_changing_source() {
    view.filter = "  REQUIRED group "
    compare(view.sections[0].rows.length, 1)
    compare(view.sections[0].rows[0].title, "Name")
    compare(view.sections[1].rows.length, 0)
    compare(view.detail.modelSections[0].rows.length, 2)
    view.filter = "people"
    compare(view.sections[0].rows[0].title, "Members")
    compare(view.sections[1].rows[0].title, "GetMembers()")
  }
  function test_filter_opens_matches_and_clearing_restores_section_choices() {
    view.setExpanded("properties", false)
    view.setExpanded("methods", true)
    view.filter = "people"
    verify(view.isExpanded("properties"))
    verify(view.isExpanded("methods"))
    view.setExpanded("methods", false)
    verify(!view.isExpanded("methods"))
    view.filter = ""
    verify(!view.isExpanded("properties"))
    verify(view.isExpanded("methods"))
  }
  function test_related_model_does_not_inherit_a_filter_that_hides_its_fields() {
    view.filter = "name"
    view.setExpanded("properties", false)
    view.detail = {safeId: "kb-related", modelSections: []}
    compare(view.filter, "")
    verify(view.isExpanded("properties"))
    verify(!view.isExpanded("methods"))
  }
  function test_non_model_detail_has_no_model_sections() {
    view.detail = {title: "Guide", body: "Read me"}
    compare(view.sections, [])
    view.detail = null
    compare(view.sections, [])
  }
}

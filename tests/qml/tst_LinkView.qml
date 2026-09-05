import QtQuick
import QtTest
import "../../plugin/oneall.rock-arch" as RockArch

TestCase {
  name: "PersonalLinkViews"
  RockArch.RockArchLinkView { id: model }
  SignalSpy { id: opened; target: model; signalName: "openRequested" }
  SignalSpy { id: expanded; target: model; signalName: "expandedChanged" }
  SignalSpy { id: added; target: model; signalName: "addLinkRequested" }
  function init() {
    model.sections = []
    model.links = [
      {safeId: "z", title: "Zulu", section: "Work", groupId: "work", isShared: false},
      {safeId: "a", title: "alpha", section: "Work", groupId: "work", isShared: false},
      {safeId: "b", title: "Beta", section: "Work", groupId: "shared", isShared: true}
    ]
    model.configure("groups", [])
    opened.clear()
    expanded.clear()
    added.clear()
  }
  function test_groups_default_collapsed_and_same_names_remain_distinct() {
    compare(model.rows.length, 2)
    compare(model.rows[0].count, 2)
    compare(model.rows[1].count, 1)
    compare(model.rows[1].isShared, true)
    verify(!model.rows[0].expanded)
  }
  function test_toggle_multiple_sections_and_open_the_correct_link() {
    model.activate(0)
    compare(model.rows.length, 4)
    compare(model.rows[1].title, "Zulu")
    compare(opened.count, 0)
    model.activate(3)
    compare(model.rows.length, 5)
    compare(model.expandedGroups, ["work", "shared"])
    model.activate(4)
    compare(opened.signalArguments[0][0], "b")
    model.activate(0)
    compare(model.rows.length, 3)
    compare(model.rows[0].expanded, false)
    compare(model.rows[1].expanded, true)
    compare(model.cursor, 0)
  }
  function test_alpha_is_flat_case_insensitive_and_restores_expansion() {
    model.expand("work", true)
    model.configure("alpha", model.expandedGroups)
    compare(model.rows.map(function(row) { return row.title }), ["alpha", "Beta", "Zulu"])
    model.activate(0)
    compare(opened.signalArguments[0][0], "a")
    model.configure("groups", model.expandedGroups)
    compare(model.rows.length, 4)
    compare(model.selected().safeId, "a")
    compare(model.expandedGroups, ["work"])
  }
  function test_horizontal_keys_expand_enter_and_collapse_without_opening() {
    verify(model.horizontal(1))
    verify(model.rows[0].expanded)
    model.horizontal(1)
    compare(model.cursor, 1)
    model.horizontal(-1)
    compare(model.cursor, 0)
    model.horizontal(-1)
    compare(model.rows.length, 2)
    compare(opened.count, 0)
  }
  function test_refresh_preserves_selection_and_handles_removed_group() {
    model.activate(0)
    model.cursor = 2
    model.replace([model.links[2], model.links[1], model.links[0]], null)
    compare(model.selected().safeId, "a")
    model.replace([model.links[0]], null)
    verify(model.cursor >= 0 && model.cursor < model.rows.length)
    compare(model.selected().sectionId, "shared")
  }
  function test_saved_link_expands_its_group_and_selects_link() {
    model.replace(model.links, {name: "alpha", section: "Work"})
    compare(model.expandedGroups, ["work"])
    compare(model.selected().safeId, "a")
    compare(expanded.count, 1)
  }
  function test_empty_private_sections_have_an_action_that_targets_the_right_section() {
    model.replace(model.links, null, [
      {groupId: "work", safeId: "private-work", name: "Work"},
      {groupId: "empty", safeId: "private-empty", name: "Projects"}
    ])
    compare(model.rows.length, 3)
    compare(model.rows[0].sectionSafeId, "private-work")
    compare(model.rows[1].sectionSafeId, undefined)
    compare(model.rows[2].count, 0)
    model.activate(2)
    compare(model.rows[3].title, "Add a link")
    model.horizontal(1)
    compare(model.cursor, 3)
    model.activate(3)
    compare(added.signalArguments[0][0], "private-empty")
    compare(opened.count, 0)
    model.horizontal(-1)
    compare(model.cursor, 2)
    model.configure("alpha", model.expandedGroups)
    compare(model.rows.length, 3)
    verify(model.rows.every(function(row) { return !row.empty && !row.group }))
  }
  function test_new_section_is_revealed_and_catalog_clears_with_account() {
    model.replace([], {kind: "section", groupId: "empty"}, [
      {groupId: "empty", safeId: "private-empty", name: "Projects"}
    ])
    compare(model.rows.length, 2)
    compare(model.selected().sectionId, "empty")
    compare(model.selected().expanded, true)
    model.replace([], null, [])
    compare(model.rows.length, 0)
    compare(model.cursor, -1)
  }
  function test_account_preferences_restore_without_writing_or_crossing_accounts() {
    model.configure("groups", ["work"])
    compare(model.rows.length, 4)
    model.configure("groups", ["shared"])
    compare(model.rows.length, 3)
    compare(model.rows[0].expanded, false)
    compare(model.rows[1].expanded, true)
    compare(expanded.count, 0)
    model.replace([], null)
    compare(model.cursor, -1)
  }
}
